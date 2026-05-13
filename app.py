from __future__ import annotations

import io
import base64
import os
import re
import shutil
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from dataclasses import dataclass
from typing import Any

from flask import Flask, Response, flash, redirect, render_template, request, send_file, url_for


app = Flask(__name__)
app.secret_key = "devsecops-starter-kit-local-secret"


RUNTIMES: dict[str, dict[str, Any]] = {
    "python": {
        "label": "Python Flask",
        "port": 8000,
        "docker_template": "artifacts/dockerfile.python.j2",
        "install_command": "pip install -r requirements.txt",
        "test_command": "python -m pytest",
        "build_context": ".",
    },
    "node": {
        "label": "Node.js",
        "port": 3000,
        "docker_template": "artifacts/dockerfile.node.j2",
        "install_command": "npm ci",
        "test_command": "npm test",
        "build_context": ".",
    },
    "java": {
        "label": "Java Spring Boot",
        "port": 8080,
        "docker_template": "artifacts/dockerfile.java.j2",
        "install_command": "mvn dependency:resolve",
        "test_command": "mvn test",
        "build_context": ".",
    },
    "go": {
        "label": "Go",
        "port": 8080,
        "docker_template": "artifacts/dockerfile.go.j2",
        "install_command": "go mod download",
        "test_command": "go test ./...",
        "build_context": ".",
    },
}

CI_SYSTEMS = {
    "jenkins": "Jenkinsfile",
    "github-actions": ".github/workflows/devsecops.yml",
}


@dataclass(frozen=True)
class StarterKitConfig:
    project_name: str
    runtime: str
    ci_system: str
    repository_url: str
    registry: str
    image_name: str
    namespace: str
    app_port: int
    replicas: int
    severity_gate: str
    include_ingress: bool
    include_hpa: bool
    include_network_policy: bool
    build_environment: str  # "vm" or "gke"

    @property
    def slug(self) -> str:
        slug = re.sub(r"[^a-z0-9-]+", "-", self.project_name.lower()).strip("-")
        return slug or "devsecops-app"

    @property
    def full_image_name(self) -> str:
        registry = self.registry.rstrip("/")
        return f"{registry}/{self.image_name}:{self.slug}-${{BUILD_NUMBER}}"

    @property
    def k8s_image_name(self) -> str:
        registry = self.registry.rstrip("/")
        return f"{registry}/{self.image_name}:latest"

    @property
    def runtime_label(self) -> str:
        return RUNTIMES[self.runtime]["label"]

    @property
    def test_command(self) -> str:
        return RUNTIMES[self.runtime]["test_command"]

    @property
    def install_command(self) -> str:
        return RUNTIMES[self.runtime]["install_command"]


@dataclass(frozen=True)
class ModuleConfig:
    name: str
    runtime: str
    path: str
    port: int
    image: str

    @property
    def test_command(self) -> str:
        return RUNTIMES[self.runtime]["test_command"]

    @property
    def install_command(self) -> str:
        return RUNTIMES[self.runtime]["install_command"]

    @property
    def runtime_label(self) -> str:
        return RUNTIMES[self.runtime]["label"]


@dataclass(frozen=True)
class AutomationConfig:
    repo_url: str
    git_branch: str
    git_username: str
    git_token: str
    git_author_name: str
    git_author_email: str
    jenkins_url: str
    jenkins_username: str
    jenkins_token: str
    jenkins_job_name: str
    docker_registry_host: str
    docker_username: str
    docker_password: str
    kubeconfig: str
    trigger_build: bool


@dataclass(frozen=True)
class AutomationResult:
    repo_url: str
    branch: str
    commit_sha: str
    jenkins_job_url: str
    build_triggered: bool
    files: list[str]


def normalize_name(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_.-]+", "-", value.strip()).strip("-._")
    return cleaned or fallback


def normalize_registry(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_./:-]+", "-", value.strip()).strip("-./:")
    return cleaned or fallback


def normalize_job_name(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9_. -]+", "-", value.strip()).strip("-. ")
    return cleaned or fallback


def parse_config(form: dict[str, str]) -> tuple[StarterKitConfig | None, list[str]]:
    errors: list[str] = []
    project_name = normalize_name(form.get("project_name", ""), "devsecops-app")
    runtime = form.get("runtime", "python")
    ci_system = form.get("ci_system", "jenkins")

    if runtime not in RUNTIMES:
        errors.append("Choose a supported runtime.")
    if ci_system not in CI_SYSTEMS:
        errors.append("Choose a supported CI system.")

    try:
        app_port = int(form.get("app_port") or RUNTIMES.get(runtime, RUNTIMES["python"])["port"])
        replicas = int(form.get("replicas") or 2)
    except ValueError:
        errors.append("Port and replicas must be numbers.")
        app_port = 8000
        replicas = 2

    if not 1 <= app_port <= 65535:
        errors.append("Application port must be between 1 and 65535.")
    if not 1 <= replicas <= 10:
        errors.append("Replicas must be between 1 and 10.")

    build_environment = form.get("build_environment", "vm")
    if build_environment not in ("vm", "gke"):
        build_environment = "vm"

    config = StarterKitConfig(
        project_name=project_name,
        runtime=runtime,
        ci_system=ci_system,
        repository_url=form.get("repository_url", "").strip(),
        registry=normalize_registry(form.get("registry", ""), "registry.example.com/team"),
        image_name=normalize_name(form.get("image_name", ""), project_name.lower()),
        namespace=normalize_name(form.get("namespace", ""), "devsecops"),
        app_port=app_port,
        replicas=replicas,
        severity_gate=form.get("severity_gate", "HIGH,CRITICAL"),
        include_ingress=form.get("include_ingress") == "on",
        include_hpa=form.get("include_hpa") == "on",
        include_network_policy=form.get("include_network_policy") == "on",
        build_environment=build_environment,
    )
    return (None, errors) if errors else (config, [])


def parse_automation_config(form: dict[str, str], starter: StarterKitConfig) -> tuple[AutomationConfig | None, list[str]]:
    errors: list[str] = []
    if starter.ci_system != "jenkins":
        errors.append("Full automation currently requires Jenkins as the CI system.")
    repo_url = form.get("repository_url", "").strip()
    jenkins_url = form.get("jenkins_url", "").strip().rstrip("/")
    required = {
        "Repository URL": repo_url,
        "Git username": form.get("git_username", "").strip(),
        "Git token": form.get("git_token", "").strip(),
        "Jenkins URL": jenkins_url,
        "Jenkins username": form.get("jenkins_username", "").strip(),
        "Jenkins API token": form.get("jenkins_token", "").strip(),
        "Docker username": form.get("docker_username", "").strip(),
        "Docker password/token": form.get("docker_password", "").strip(),
        "Kubeconfig": form.get("kubeconfig", "").strip(),
    }
    for label, value in required.items():
        if not value:
            errors.append(f"{label} is required for full automation.")

    if repo_url and not repo_url.startswith(("https://", "http://")):
        errors.append("Repository URL must be an HTTPS Git URL for automated push.")
    if jenkins_url and not jenkins_url.startswith(("https://", "http://")):
        errors.append("Jenkins URL must start with http:// or https://.")

    automation = AutomationConfig(
        repo_url=repo_url,
        git_branch=normalize_name(form.get("git_branch", ""), "main"),
        git_username=form.get("git_username", "").strip(),
        git_token=form.get("git_token", "").strip(),
        git_author_name=form.get("git_author_name", "").strip() or "DevSecOps Generator",
        git_author_email=form.get("git_author_email", "").strip() or "devsecops-generator@example.com",
        jenkins_url=jenkins_url,
        jenkins_username=form.get("jenkins_username", "").strip(),
        jenkins_token=form.get("jenkins_token", "").strip(),
        jenkins_job_name=normalize_job_name(form.get("jenkins_job_name", ""), starter.slug),
        docker_registry_host=form.get("docker_registry_host", "").strip() or starter.registry.split("/")[0],
        docker_username=form.get("docker_username", "").strip(),
        docker_password=form.get("docker_password", "").strip(),
        kubeconfig=form.get("kubeconfig", "").strip(),
        trigger_build=form.get("trigger_build") == "on",
    )
    return (None, errors) if errors else (automation, [])


def parse_modules(form: dict[str, str]) -> list[ModuleConfig]:
    """Parse dynamically added modules from the form."""
    modules: list[ModuleConfig] = []
    names = form.getlist("module_name") if hasattr(form, "getlist") else []
    runtimes = form.getlist("module_runtime") if hasattr(form, "getlist") else []
    paths = form.getlist("module_path") if hasattr(form, "getlist") else []
    ports = form.getlist("module_port") if hasattr(form, "getlist") else []
    images = form.getlist("module_image") if hasattr(form, "getlist") else []

    for i in range(len(names)):
        name = normalize_name(names[i] if i < len(names) else "", "")
        if not name:
            continue
        runtime = runtimes[i] if i < len(runtimes) else "python"
        if runtime not in RUNTIMES:
            runtime = "python"
        path = (paths[i] if i < len(paths) else name).strip() or name
        try:
            port = int(ports[i]) if i < len(ports) and ports[i] else RUNTIMES[runtime]["port"]
        except ValueError:
            port = RUNTIMES[runtime]["port"]
        image = normalize_name(images[i] if i < len(images) else "", name)
        modules.append(ModuleConfig(name=name, runtime=runtime, path=path, port=port, image=image))
    return modules


def render_artifacts(config: StarterKitConfig, modules: list[ModuleConfig] | None = None) -> dict[str, str]:
    context = {"config": config, "runtimes": RUNTIMES}

    if modules and len(modules) > 1:
        return render_multimodule_artifacts(config, modules)

    artifacts = {
        "Dockerfile": render_template(RUNTIMES[config.runtime]["docker_template"], **context),
        "README.md": render_template("artifacts/readme.md.j2", **context),
        "k8s/deployment.yaml": render_template("artifacts/k8s/deployment.yaml.j2", **context),
        "k8s/service.yaml": render_template("artifacts/k8s/service.yaml.j2", **context),
        "k8s/configmap.yaml": render_template("artifacts/k8s/configmap.yaml.j2", **context),
        "k8s/secret.example.yaml": render_template("artifacts/k8s/secret.example.yaml.j2", **context),
        "security/trivy.yaml": render_template("artifacts/security/trivy.yaml.j2", **context),
        "security/checkov.yaml": render_template("artifacts/security/checkov.yaml.j2", **context),
        ".dockerignore": render_template("artifacts/dockerignore.j2", **context),
    }

    if config.ci_system == "jenkins":
        artifacts[CI_SYSTEMS[config.ci_system]] = render_template("artifacts/Jenkinsfile.j2", **context)
    else:
        artifacts[CI_SYSTEMS[config.ci_system]] = render_template("artifacts/github-actions.yml.j2", **context)

    if config.include_ingress:
        artifacts["k8s/ingress.yaml"] = render_template("artifacts/k8s/ingress.yaml.j2", **context)
    if config.include_hpa:
        artifacts["k8s/hpa.yaml"] = render_template("artifacts/k8s/hpa.yaml.j2", **context)
    if config.include_network_policy:
        artifacts["k8s/networkpolicy.yaml"] = render_template("artifacts/k8s/networkpolicy.yaml.j2", **context)

    return artifacts


def render_multimodule_artifacts(config: StarterKitConfig, modules: list[ModuleConfig]) -> dict[str, str]:
    """Generate artifacts for a multi-module repo (e.g. frontend + backend)."""
    context = {"config": config, "runtimes": RUNTIMES, "modules": modules}
    artifacts: dict[str, str] = {
        "security/trivy.yaml": render_template("artifacts/security/trivy.yaml.j2", **context),
        "security/checkov.yaml": render_template("artifacts/security/checkov.yaml.j2", **context),
    }

    # Per-module: Dockerfile, K8s manifests
    for module in modules:
        mod_ctx = {"config": config, "module": module, "runtimes": RUNTIMES}
        artifacts[f"{module.path}/Dockerfile"] = render_template(RUNTIMES[module.runtime]["docker_template"], config=config, **mod_ctx)
        artifacts[f"{module.path}/.dockerignore"] = render_template("artifacts/dockerignore.j2", **mod_ctx)
        artifacts[f"k8s/{module.name}-deployment.yaml"] = render_template("artifacts/k8s/module-deployment.yaml.j2", **mod_ctx)
        artifacts[f"k8s/{module.name}-service.yaml"] = render_template("artifacts/k8s/module-service.yaml.j2", **mod_ctx)
        artifacts[f"k8s/{module.name}-configmap.yaml"] = render_template("artifacts/k8s/module-configmap.yaml.j2", **mod_ctx)
        artifacts[f"k8s/{module.name}-secret.example.yaml"] = render_template("artifacts/k8s/module-secret.example.yaml.j2", **mod_ctx)
        if config.include_hpa:
            artifacts[f"k8s/{module.name}-hpa.yaml"] = render_template("artifacts/k8s/module-hpa.yaml.j2", **mod_ctx)

    # Shared ingress routing to all modules
    if config.include_ingress:
        artifacts["k8s/ingress.yaml"] = render_template("artifacts/k8s/module-ingress.yaml.j2", **context)

    if config.include_network_policy:
        artifacts["k8s/networkpolicy.yaml"] = render_template("artifacts/k8s/networkpolicy.yaml.j2", **context)

    # Unified pipeline
    if config.ci_system == "jenkins":
        artifacts["Jenkinsfile"] = render_template("artifacts/Jenkinsfile.multimodule.j2", **context)
    else:
        artifacts[CI_SYSTEMS[config.ci_system]] = render_template("artifacts/github-actions.yml.j2", **context)

    return artifacts


def add_sample_application(artifacts: dict[str, str], config: StarterKitConfig) -> None:
    context = {"config": config, "runtimes": RUNTIMES}
    if config.runtime == "python":
        artifacts["app.py"] = render_template("samples/python/app.py.j2", **context)
        artifacts["requirements.txt"] = "Flask==3.0.3\n"
    elif config.runtime == "node":
        artifacts["package.json"] = render_template("samples/node/package.json.j2", **context)
        artifacts["server.js"] = render_template("samples/node/server.js.j2", **context)
    elif config.runtime == "java":
        artifacts["pom.xml"] = render_template("samples/java/pom.xml.j2", **context)
        artifacts["src/main/java/com/example/App.java"] = render_template("samples/java/App.java.j2", **context)
    elif config.runtime == "go":
        artifacts["go.mod"] = render_template("samples/go/go.mod.j2", **context)
        artifacts["main.go"] = render_template("samples/go/main.go.j2", **context)


def run_command(args: list[str], cwd: str, env: dict[str, str] | None = None) -> str:
    completed = subprocess.run(
        args,
        cwd=cwd,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        message = completed.stderr.strip() or completed.stdout.strip() or f"Command failed: {' '.join(args)}"
        raise RuntimeError(message)
    return completed.stdout.strip()


def authenticated_repo_url(repo_url: str, username: str, token: str) -> str:
    parsed = urllib.parse.urlsplit(repo_url)
    username = urllib.parse.quote(username, safe="")
    token = urllib.parse.quote(token, safe="")
    netloc = f"{username}:{token}@{parsed.netloc}"
    return urllib.parse.urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))


def write_artifacts(target: str, artifacts: dict[str, str]) -> list[str]:
    written: list[str] = []
    for relative_path, content in artifacts.items():
        full_path = os.path.join(target, *relative_path.split("/"))
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        with open(full_path, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        written.append(relative_path)
    return sorted(written)


def push_repository(artifacts: dict[str, str], starter: StarterKitConfig, automation: AutomationConfig) -> tuple[str, list[str]]:
    workdir = tempfile.mkdtemp(prefix="devsecops-kit-")
    try:
        files = write_artifacts(workdir, artifacts)
        env = os.environ.copy()
        env["GIT_TERMINAL_PROMPT"] = "0"
        run_command(["git", "init"], workdir, env)
        run_command(["git", "checkout", "-B", automation.git_branch], workdir, env)
        run_command(["git", "config", "user.name", automation.git_author_name], workdir, env)
        run_command(["git", "config", "user.email", automation.git_author_email], workdir, env)
        run_command(["git", "add", "."], workdir, env)
        run_command(["git", "commit", "-m", f"Add {starter.project_name} DevSecOps starter kit"], workdir, env)
        commit_sha = run_command(["git", "rev-parse", "HEAD"], workdir, env)
        run_command(["git", "remote", "add", "origin", authenticated_repo_url(automation.repo_url, automation.git_username, automation.git_token)], workdir, env)
        run_command(["git", "push", "-u", "--force", "origin", automation.git_branch], workdir, env)
        return commit_sha, files
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def jenkins_request(
    automation: AutomationConfig,
    path: str,
    method: str = "GET",
    data: bytes | None = None,
    content_type: str | None = None,
    include_crumb: bool = True,
) -> bytes:
    url = f"{automation.jenkins_url}/{path.lstrip('/')}"
    headers: dict[str, str] = {}
    if content_type:
        headers["Content-Type"] = content_type
    credentials = f"{automation.jenkins_username}:{automation.jenkins_token}".encode("utf-8")
    headers["Authorization"] = "Basic " + base64.b64encode(credentials).decode("ascii")

    if include_crumb:
        crumb = get_jenkins_crumb(automation)
        if crumb:
            headers[crumb["crumbRequestField"]] = crumb["crumb"]

    request_obj = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request_obj, timeout=30) as response:
            return response.read()
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Jenkins request failed ({exc.code}) for {path}: {body}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Could not reach Jenkins: {exc.reason}") from exc


def get_jenkins_crumb(automation: AutomationConfig) -> dict[str, str] | None:
    try:
        body = jenkins_request(automation, "/crumbIssuer/api/json", include_crumb=False)
    except RuntimeError:
        return None
    import json

    return json.loads(body.decode("utf-8"))


def credential_xml(credential_id: str, description: str, username: str | None = None, secret: str = "") -> bytes:
    import html

    if username is None:
        xml = f"""<org.jenkinsci.plugins.plaincredentials.impl.StringCredentialsImpl>
  <scope>GLOBAL</scope>
  <id>{html.escape(credential_id)}</id>
  <description>{html.escape(description)}</description>
  <secret>{html.escape(secret)}</secret>
</org.jenkinsci.plugins.plaincredentials.impl.StringCredentialsImpl>"""
    else:
        xml = f"""<com.cloudbees.plugins.credentials.impl.UsernamePasswordCredentialsImpl>
  <scope>GLOBAL</scope>
  <id>{html.escape(credential_id)}</id>
  <description>{html.escape(description)}</description>
  <username>{html.escape(username)}</username>
  <password>{html.escape(secret)}</password>
</com.cloudbees.plugins.credentials.impl.UsernamePasswordCredentialsImpl>"""
    return xml.encode("utf-8")


def create_or_update_credential(
    automation: AutomationConfig,
    credential_id: str,
    description: str,
    username: str | None,
    secret: str,
) -> None:
    delete_path = f"/credentials/store/system/domain/_/credential/{urllib.parse.quote(credential_id, safe='')}/doDelete"
    try:
        jenkins_request(automation, delete_path, method="POST", data=b"")
    except RuntimeError:
        pass

    data = credential_xml(credential_id, description, username=username, secret=secret)
    jenkins_request(
        automation,
        "/credentials/store/system/domain/_/createCredentials",
        method="POST",
        data=data,
        content_type="application/xml",
    )


def jenkins_job_xml(starter: StarterKitConfig, automation: AutomationConfig) -> bytes:
    import html

    repo_url = html.escape(automation.repo_url)
    branch = html.escape(automation.git_branch)
    git_credentials_id = html.escape(f"{starter.slug}-git")
    xml = f"""<?xml version='1.1' encoding='UTF-8'?>
<flow-definition plugin="workflow-job">
  <actions/>
  <description>Generated by Automated DevSecOps CI/CD Starter Kit Generator.</description>
  <keepDependencies>false</keepDependencies>
  <properties/>
  <definition class="org.jenkinsci.plugins.workflow.cps.CpsScmFlowDefinition" plugin="workflow-cps">
    <scm class="hudson.plugins.git.GitSCM" plugin="git">
      <configVersion>2</configVersion>
      <userRemoteConfigs>
        <hudson.plugins.git.UserRemoteConfig>
          <url>{repo_url}</url>
          <credentialsId>{git_credentials_id}</credentialsId>
        </hudson.plugins.git.UserRemoteConfig>
      </userRemoteConfigs>
      <branches>
        <hudson.plugins.git.BranchSpec>
          <name>*/{branch}</name>
        </hudson.plugins.git.BranchSpec>
      </branches>
      <doGenerateSubmoduleConfigurations>false</doGenerateSubmoduleConfigurations>
      <submoduleCfg class="empty-list"/>
      <extensions/>
    </scm>
    <scriptPath>Jenkinsfile</scriptPath>
    <lightweight>true</lightweight>
  </definition>
  <triggers/>
  <disabled>false</disabled>
</flow-definition>"""
    return xml.encode("utf-8")


def create_or_update_jenkins_job(starter: StarterKitConfig, automation: AutomationConfig) -> str:
    create_or_update_credential(automation, f"{starter.slug}-git", "Git token for generated DevSecOps job", automation.git_username, automation.git_token)
    create_or_update_credential(automation, f"{starter.slug}-docker", "Docker registry credentials", automation.docker_username, automation.docker_password)
    create_or_update_credential(automation, f"{starter.slug}-kubeconfig", "Kubernetes kubeconfig", None, automation.kubeconfig)

    job_name = urllib.parse.quote(automation.jenkins_job_name, safe="")
    config_xml = jenkins_job_xml(starter, automation)
    try:
        jenkins_request(automation, f"/job/{job_name}/config.xml", method="POST", data=config_xml, content_type="application/xml")
    except RuntimeError:
        jenkins_request(
            automation,
            f"/createItem?name={job_name}",
            method="POST",
            data=config_xml,
            content_type="application/xml",
        )

    if automation.trigger_build:
        jenkins_request(automation, f"/job/{job_name}/build", method="POST", data=b"")

    return f"{automation.jenkins_url}/job/{urllib.parse.quote(automation.jenkins_job_name, safe='')}/"


def run_full_automation(starter: StarterKitConfig, automation: AutomationConfig, modules: list[ModuleConfig] | None = None) -> AutomationResult:
    artifacts = render_artifacts(starter, modules)
    add_sample_application(artifacts, starter)
    commit_sha, files = push_repository(artifacts, starter, automation)
    job_url = create_or_update_jenkins_job(starter, automation)
    return AutomationResult(
        repo_url=automation.repo_url,
        branch=automation.git_branch,
        commit_sha=commit_sha,
        jenkins_job_url=job_url,
        build_triggered=automation.trigger_build,
        files=files,
    )


@app.get("/")
def index() -> str:
    return render_template("index.html", runtimes=RUNTIMES, ci_systems=CI_SYSTEMS)


@app.post("/generate")
def generate() -> Response:
    config, errors = parse_config(request.form)
    if errors or config is None:
        for error in errors:
            flash(error, "error")
        return redirect(url_for("index"))

    modules = parse_modules(request.form)
    artifacts = render_artifacts(config, modules)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as kit:
        for path, content in artifacts.items():
            kit.writestr(f"{config.slug}/{path}", content)
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"{config.slug}-devsecops-starter-kit.zip",
        mimetype="application/zip",
    )


@app.post("/automate")
def automate() -> str | Response:
    starter, starter_errors = parse_config(request.form)
    if starter_errors or starter is None:
        for error in starter_errors:
            flash(error, "error")
        return redirect(url_for("index"))

    automation, automation_errors = parse_automation_config(request.form, starter)
    if automation_errors or automation is None:
        for error in automation_errors:
            flash(error, "error")
        return redirect(url_for("index"))

    try:
        modules = parse_modules(request.form)
        result = run_full_automation(starter, automation, modules)
    except Exception as exc:
        flash(str(exc), "error")
        return redirect(url_for("index"))

    return render_template("result.html", result=result, config=starter)


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)

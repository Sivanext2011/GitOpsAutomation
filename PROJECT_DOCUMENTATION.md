# Automated DevSecOps CI/CD Starter Kit Generator - Project Documentation

## 1. Project Overview

The Automated DevSecOps CI/CD Starter Kit Generator is a Flask web application that creates ready-to-use DevSecOps starter kits for application teams. It collects project metadata through a browser form and generates CI/CD, container, Kubernetes, and security scanning artifacts.

The project supports two main workflows:

1. Generate and download a ZIP file containing DevSecOps starter files.
2. Push generated files to a Git repository, configure a Jenkins Pipeline job, create Jenkins credentials, and optionally trigger the first build.

The generated starter kit is intended to help teams bootstrap a secure delivery pipeline quickly instead of manually writing Dockerfiles, Jenkinsfiles, GitHub Actions workflows, Kubernetes manifests, and security scanner configuration from scratch.

## 2. Core Capabilities

- Generates runtime-aware Dockerfiles for Python Flask, Node.js, Java Spring Boot, and Go applications.
- Generates Jenkins or GitHub Actions CI/CD pipelines.
- Supports VM/Docker-daemon builds and GKE/Kubernetes builds with Kaniko for Jenkins.
- Adds Trivy dependency and container image scanning.
- Adds Syft SBOM generation.
- Adds Checkov Infrastructure-as-Code scanning.
- Generates Kubernetes Deployment, Service, ConfigMap, Secret example, Ingress, HPA, and NetworkPolicy manifests.
- Supports single-service and multi-module repositories.
- Packages generated files as a downloadable ZIP.
- Can push generated files to Git and configure Jenkins automatically.
- Creates Jenkins credentials for Git, Docker registry access, and Kubernetes kubeconfig.
- Creates the Jenkins Kubernetes cloud automatically for GKE/Kubernetes build mode.

## 3. Technology Stack

The application itself uses:

- Python
- Flask 3.0.3
- Werkzeug 3.0.3
- Jinja2 templates through Flask
- HTML, CSS, and small client-side JavaScript

The generated DevSecOps starter kits can use:

- Docker
- Jenkins Pipeline
- GitHub Actions
- Kubernetes
- Trivy
- Syft
- Checkov
- kubectl
- Kaniko for Kubernetes-based image builds

## 4. Repository Structure

```text
.
|-- app.py
|-- README.md
|-- PROJECT_DOCUMENTATION.md
|-- requirements.txt
|-- static/
|   `-- styles.css
`-- templates/
    |-- index.html
    |-- result.html
    |-- artifacts/
    |   |-- Dockerfile templates
    |   |-- Jenkins and GitHub Actions templates
    |   |-- Kubernetes manifest templates
    |   |-- security scanner templates
    |   `-- generated README template
    `-- samples/
        |-- python/
        |-- node/
        |-- java/
        `-- go/
```

### Important Files

| File or Directory | Purpose |
| --- | --- |
| `app.py` | Main Flask application, form parsing, artifact rendering, ZIP generation, Git push, and Jenkins automation. |
| `templates/index.html` | Main web form used to collect project, CI/CD, registry, Kubernetes, module, and Jenkins inputs. |
| `templates/result.html` | Result page shown after successful full Jenkins automation. |
| `templates/artifacts/` | Jinja2 templates used to generate Dockerfiles, pipelines, Kubernetes files, scanner configs, and generated project README. |
| `templates/artifacts/k8s/` | Kubernetes templates for single-service and multi-module deployments. |
| `templates/artifacts/security/` | Security scanning configuration templates. |
| `templates/samples/` | Sample application templates for supported runtimes. |
| `static/styles.css` | Styling for the Flask web UI. |
| `requirements.txt` | Python dependencies required to run the generator. |

## 5. Application Architecture

The application follows a simple server-rendered Flask architecture:

1. The user opens the form at `/`.
2. The form submits to either `/generate` or `/automate`.
3. Flask validates and normalizes the submitted values.
4. Jinja2 artifact templates are rendered using the validated configuration.
5. The application either returns a ZIP file or performs full Git and Jenkins automation.

There is no database. User inputs and credentials are handled during the request lifecycle. Generated ZIP contents are created in memory using `io.BytesIO`.

## 6. Runtime Configuration Model

The supported runtimes are defined in `RUNTIMES` inside `app.py`.

| Runtime Key | Label | Default Port | Install Command | Test Command |
| --- | --- | ---: | --- | --- |
| `python` | Python Flask | 8000 | `pip install -r requirements.txt` | `python -m pytest` |
| `node` | Node.js | 3000 | `npm ci` | `npm test` |
| `java` | Java Spring Boot | 8080 | `mvn dependency:resolve` | `mvn test` |
| `go` | Go | 8080 | `go mod download` | `go test ./...` |

Each runtime maps to a specific Dockerfile template in `templates/artifacts/`.

## 7. Web Routes

### `GET /`

Renders the main generator form.

The form includes sections for:

- Project metadata
- Runtime selection
- CI system selection
- Build environment
- Container registry and image details
- Kubernetes namespace, port, and replica settings
- Optional multi-module configuration
- Optional Kubernetes artifacts
- Vulnerability scanning options
- Git automation credentials
- Jenkins automation credentials
- Docker registry credentials
- Kubernetes kubeconfig

### `POST /generate`

Generates a ZIP file and returns it to the browser.

Main behavior:

1. Parses the submitted form into a `StarterKitConfig`.
2. Parses optional module definitions.
3. Renders the artifact templates.
4. Writes generated files into an in-memory ZIP archive.
5. Sends the ZIP as a download named:

```text
<project-slug>-devsecops-starter-kit.zip
```

No Git or Jenkins changes are made in this mode.

### `POST /automate`

Runs full automation for Jenkins-based projects.

Main behavior:

1. Parses the starter kit configuration.
2. Validates Jenkins automation inputs.
3. Renders the generated artifacts.
4. Clones or initializes the target Git repository.
5. Writes generated CI/CD files into the repository.
6. Commits and pushes changes when needed.
7. Creates or updates Jenkins credentials.
8. For GKE/Kubernetes build mode, creates or updates the Jenkins Kubernetes cloud.
9. Creates or updates the Jenkins Pipeline job.
10. Optionally triggers a Jenkins build.
11. Shows the result page with repository, branch, commit, Jenkins job URL, and pushed files.

Full automation currently requires Jenkins as the selected CI system.

## 8. Configuration Data Classes

### `StarterKitConfig`

Represents the primary project configuration.

Important fields:

- `project_name`
- `runtime`
- `ci_system`
- `repository_url`
- `registry`
- `image_name`
- `namespace`
- `app_port`
- `replicas`
- `severity_gate`
- `include_ingress`
- `include_hpa`
- `include_network_policy`
- `skip_vuln_scan`
- `deploy_branch`
- `build_environment`

Important computed properties:

- `slug`: URL- and filename-safe project name.
- `full_image_name`: Build-number-tagged image used by Jenkins.
- `k8s_image_name`: `latest` image reference used in Kubernetes manifests.
- `runtime_label`: Human-readable runtime label.
- `install_command`: Runtime-specific dependency installation command.
- `test_command`: Runtime-specific test command.

### `ModuleConfig`

Represents one module in a multi-module repository.

Important fields:

- `name`
- `runtime`
- `path`
- `port`
- `image`

This allows the generator to create per-module Dockerfiles, Kubernetes manifests, and pipeline stages.

### `AutomationConfig`

Represents Git, Jenkins, Docker registry, and Kubernetes credentials for full automation.

Important fields:

- Git repository URL, branch, username, token, author name, and author email
- Jenkins URL, username, API token, and job name
- Docker registry host, username, and password/token
- Kubernetes kubeconfig
- Build trigger option

### `AutomationResult`

Represents the output from the full automation workflow.

It includes:

- Repository URL
- Branch
- Commit SHA
- Jenkins job URL
- Whether a build was triggered
- List of files written to the repository

## 9. Generated Artifact Types

### Container Artifacts

The generator creates a runtime-specific `Dockerfile`.

Supported templates:

- `dockerfile.python.j2`
- `dockerfile.node.j2`
- `dockerfile.java.j2`
- `dockerfile.go.j2`

It also creates `.dockerignore`.

### CI/CD Artifacts

For Jenkins:

- `Jenkinsfile`

For GitHub Actions:

- `.github/workflows/devsecops.yml`

For multi-module Jenkins projects:

- `Jenkinsfile` rendered from `Jenkinsfile.multimodule.j2`

### Kubernetes Artifacts

Single-service projects can generate:

- `k8s/deployment.yaml`
- `k8s/service.yaml`
- `k8s/configmap.yaml`
- `k8s/secret.example.yaml`
- `k8s/ingress.yaml`
- `k8s/hpa.yaml`
- `k8s/networkpolicy.yaml`

Multi-module projects generate per-module equivalents:

- `k8s/<module>-deployment.yaml`
- `k8s/<module>-service.yaml`
- `k8s/<module>-configmap.yaml`
- `k8s/<module>-secret.example.yaml`
- `k8s/<module>-hpa.yaml`

They can also include shared ingress and network policy manifests.

### Security Artifacts

Generated security files include:

- `security/trivy.yaml`
- `security/checkov.yaml`
- `.checkov.yaml`

The CI/CD pipeline uses these concepts for:

- Filesystem dependency scanning
- Container image vulnerability scanning
- SBOM creation
- Kubernetes manifest scanning

### Documentation Artifact

The generated starter kit includes its own `README.md`, rendered from:

```text
templates/artifacts/readme.md.j2
```

## 10. Single-Service Generation Flow

For a normal single-service project, `render_artifacts()` creates:

```text
Dockerfile
README.md
k8s/deployment.yaml
k8s/service.yaml
k8s/configmap.yaml
k8s/secret.example.yaml
security/trivy.yaml
security/checkov.yaml
.checkov.yaml
.dockerignore
Jenkinsfile or .github/workflows/devsecops.yml
```

Optional files are added based on form selections:

- `k8s/ingress.yaml`
- `k8s/hpa.yaml`
- `k8s/networkpolicy.yaml`

## 11. Multi-Module Generation Flow

When more than one module is provided, `render_multimodule_artifacts()` is used.

Each module receives:

- A Dockerfile inside the module path
- A `.dockerignore` inside the module path
- Kubernetes Deployment, Service, ConfigMap, Secret example, and optionally HPA manifests

The generated pipeline contains repeated test, build, scan, SBOM, push, and deploy behavior for each module.

This is useful for repositories such as:

```text
frontend/
backend/
worker/
```

Each module can use a different runtime, port, image name, and source path.

## 12. Jenkins Pipeline Behavior

The generated Jenkins pipeline has two modes.

### VM / Docker Daemon Mode

This mode uses `agent any` and expects the Jenkins agent to have local tools installed.

Typical stages:

1. Checkout
2. Install Dependencies
3. Unit Test
4. Build Image
5. Dependency Scan
6. Container Scan
7. SBOM
8. IaC Scan
9. Push
10. Deploy

Expected tools on the Jenkins agent:

```text
git
docker
trivy
syft
checkov
kubectl
```

### GKE / Kubernetes Mode

This mode uses the Jenkins Kubernetes agent and Kaniko.

Typical containers:

- `jnlp` for Jenkins agent communication
- `kaniko` for image build and push
- `tools` for install, test, scan, SBOM, Checkov, and kubectl commands
- `kubectl` for Kubernetes deployment commands

This mode is designed for clusters where Docker daemon access is not available or not preferred.

Full automation creates or updates a Jenkins Kubernetes cloud named `kubernetes` for this mode. The cloud uses the in-cluster Kubernetes API endpoint `https://kubernetes.default.svc`, detects the Jenkins pod namespace when possible, and enables WebSocket agents so TCP port `50000` does not need to be exposed. GKE mode deploys with the Jenkins agent pod service account, avoiding local-user kubeconfigs that require `gke-gcloud-auth-plugin`.

GKE/Kubernetes generated kits also include `jenkins/agent-rbac.yaml`, which grants the Jenkins service account permission to create, list, watch, and delete agent pods in the `jenkins` namespace. This manifest must be applied by a Kubernetes identity with RBAC administration permission.

The generated `tools` container is runtime-specific. Python projects use `python:3.12-slim`, Node.js projects use `node:22-bookworm-slim`, Java projects use `maven:3.9.9-eclipse-temurin-21`, and Go projects use `golang:1.23-bookworm`. Deployment runs in a separate `alpine:3.20` container, installs `kubectl` during the deploy stage, and creates an in-cluster kubeconfig from the mounted Jenkins agent service account token.

## 13. GitHub Actions Pipeline Behavior

The generated GitHub Actions workflow runs on:

- Pushes to `main`
- Pull requests

The generated job:

1. Checks out the repository.
2. Runs the runtime-specific test command.
3. Builds the Docker image.
4. Runs Trivy filesystem scanning.
5. Runs Trivy container image scanning.
6. Generates an SBOM using Anchore's SBOM action.
7. Runs Checkov against the `k8s` directory.

The current GitHub Actions template focuses on build, test, and scan. It does not push images or deploy to Kubernetes by default.

## 14. Full Automation Flow

Full automation is implemented by `run_full_automation()`.

High-level flow:

1. Render starter kit artifacts.
2. Clone the target Git repository using an authenticated HTTPS URL.
3. If cloning the branch fails, initialize a fresh repository and branch.
4. Write generated artifacts into the working tree.
5. Configure Git author identity.
6. Stage all changes.
7. Commit and push if changes exist.
8. Create or update Jenkins credentials.
9. For GKE/Kubernetes build mode, create or update the Jenkins Kubernetes cloud.
10. Create or update the Jenkins Pipeline job.
11. Trigger the build if requested.

The temporary repository is created using `tempfile.mkdtemp()` and removed after the operation with `shutil.rmtree()`.

## 15. Jenkins Credentials Created

Full automation creates or replaces three Jenkins credentials:

| Credential ID | Type | Purpose |
| --- | --- | --- |
| `<project-slug>-git` | Username/password | Allows Jenkins to clone the Git repository. |
| `<project-slug>-docker` | Username/password | Allows the pipeline to log in to the Docker registry. |
| `<project-slug>-kubeconfig` | Secret text | Stores kubeconfig content for VM mode or external-cluster deployment. |

The Jenkins job is configured as a Pipeline job that reads `Jenkinsfile` from SCM.

For GKE/Kubernetes mode, the Jenkins API user must have Overall/Administer permission because the app configures the Kubernetes cloud through Jenkins' script endpoint. Jenkins must have the Kubernetes plugin installed, and the Jenkins pod's service account must be allowed to create agent pods.

## 16. Input Validation and Normalization

The application sanitizes important values before using them in generated files.

Examples:

- Project names are normalized with `normalize_name()`.
- Registry values are normalized with `normalize_registry()`.
- Docker Hub browser URLs such as `https://hub.docker.com/repositories/<user>` are converted to image prefixes such as `docker.io/<user>`.
- Image names are normalized to lowercase Docker-safe names.
- Docker Hub pushes use the Docker Hub auth endpoint `https://index.docker.io/v1/` while keeping image destinations in `docker.io/<user>/<image>` form.
- Jenkins job names are normalized with `normalize_job_name()`.
- Ports must be between `1` and `65535`.
- Replicas must be between `1` and `10`.
- Runtime and CI system must be supported values.
- Full automation requires HTTPS Git repository URLs.
- Jenkins URL must start with `http://` or `https://`.

## 17. Security Model

The application handles sensitive values such as Git tokens, Jenkins API tokens, Docker registry passwords, and kubeconfig content.

Important security characteristics:

- Credentials are read from form submissions.
- Credentials are not written into the generated Git repository.
- Jenkins credentials are stored in Jenkins credential storage.
- The generated Jenkins pipeline retrieves secrets through Jenkins credentials binding.
- The generated repository contains only examples for Kubernetes secrets, not real secret values.

Production recommendations:

- Run the Flask app only in a trusted internal environment.
- Replace the hard-coded Flask secret key before production use.
- Serve the app over HTTPS if credentials are entered through the UI.
- Use short-lived tokens when possible.
- Restrict Jenkins credentials to the minimum required scope.
- Rotate tokens after demos or testing.
- Avoid storing real kubeconfig files in source control.
- Use a managed secret store for production Kubernetes applications.

## 18. Local Setup

Create and activate a virtual environment:

```powershell
python -m venv .venv
.venv\Scripts\activate
```

Install dependencies:

```powershell
pip install -r requirements.txt
```

Run the Flask app:

```powershell
python app.py
```

Open:

```text
http://127.0.0.1:5000
```

## 19. How to Generate a ZIP Starter Kit

1. Open the application in a browser.
2. Fill in project name, runtime, CI system, registry, image, namespace, port, and replicas.
3. Choose whether to include Ingress, HPA, and NetworkPolicy.
4. Choose whether to skip vulnerability scanning.
5. Leave Jenkins and Git credential fields empty if you only want the ZIP.
6. Click `Generate ZIP`.

The browser downloads a ZIP containing generated DevSecOps artifacts.

## 20. How to Use Full Jenkins Automation

1. Select Jenkins as the CI system.
2. Enter the Git repository URL and target branch.
3. Enter Git username and token.
4. Enter Jenkins URL, Jenkins username, and Jenkins API token.
5. Enter Docker registry credentials.
6. Paste Kubernetes kubeconfig content.
7. Choose whether to trigger the Jenkins build immediately.
8. Click `Push and Configure Jenkins`.

After success, the result page shows:

- Target repository
- Branch
- Commit SHA
- Jenkins job URL
- Whether the build was triggered
- Files pushed to Git

## 21. Required Jenkins Plugins and Tools

Recommended Jenkins plugins:

- Pipeline
- Git
- Credentials
- Credentials Binding
- Kubernetes plugin, if using GKE/Kubernetes agent mode

Required command-line tools for VM/Docker daemon mode:

```text
git
docker
trivy
syft
checkov
kubectl
```

For GKE/Kubernetes mode, make sure the Jenkins Kubernetes agent image or tools container has the required utilities available. The current template uses `alpine:3.20` as the tools container, so production usage may require a custom tools image with `trivy`, `syft`, `checkov`, and `kubectl` preinstalled.

## 22. Build Environment Options

### VM / Docker Daemon

Use this when Jenkins runs on a VM or node with Docker installed.

Pros:

- Simple to understand.
- Works with traditional Jenkins agents.
- Uses normal `docker build`, `docker tag`, `docker push` commands.

Considerations:

- Requires Docker daemon access.
- Jenkins agent must be trusted because Docker access is powerful.

### GKE / Kubernetes

Use this when Jenkins uses Kubernetes-based agents.

Pros:

- Avoids Docker daemon dependency.
- Uses Kaniko to build and push images.
- Fits cloud-native Jenkins deployments.

Considerations:

- Requires Jenkins Kubernetes plugin configuration.
- Requires working registry credentials.
- May need a custom tools container image.

## 23. Common Troubleshooting

### The app does not start

Check that dependencies are installed:

```powershell
pip install -r requirements.txt
```

Then run:

```powershell
python app.py
```

### ZIP generation works but Jenkins automation fails

Check:

- Repository URL starts with `https://`.
- Git username and token are valid.
- The target branch exists or the token can create/push the branch.
- Jenkins URL is reachable from the machine running Flask.
- Jenkins API token is valid.
- Jenkins user has permission to create credentials and jobs.

### Jenkins build fails during tool commands

Check that the Jenkins agent has:

```text
docker
trivy
syft
checkov
kubectl
```

Also verify the application repository contains the files expected by the selected runtime, such as `requirements.txt`, `package.json`, `pom.xml`, or `go.mod`.

### Kubernetes deploy fails

Check:

- Kubeconfig content is valid.
- The Jenkins credential `<project-slug>-kubeconfig` exists.
- The Kubernetes user has permission to create namespaces and apply manifests.
- The image registry is accessible from the cluster.
- The generated image name matches the pushed image.

### Container scan fails

This is expected when vulnerabilities at or above the configured severity gate are found.

Options:

- Fix or upgrade vulnerable dependencies.
- Adjust the vulnerability gate.
- Temporarily enable `Skip vulnerability scanning` for non-production testing.

## 24. Known Limitations

- Full automation currently supports Jenkins only.
- GitHub Actions generation does not currently include image push or Kubernetes deployment.
- The Flask secret key is hard-coded and should be changed before production use.
- The application has no authentication layer.
- Credentials are submitted through a web form, so production usage should require HTTPS and access controls.
- The GKE/Kubernetes Jenkins tools container may need customization before real use.
- Sample application generation exists in code but is not currently wired into the main ZIP generation route.

## 25. Suggested Future Enhancements

- Add authentication and role-based access for the generator UI.
- Move the Flask secret key to an environment variable.
- Add automated tests for form parsing, artifact rendering, ZIP generation, and Jenkins XML creation.
- Add GitHub Actions deployment and registry push support.
- Add Azure DevOps or GitLab CI template support.
- Add optional Helm chart generation.
- Add support for image signing with Cosign.
- Add policy-as-code examples with OPA Gatekeeper or Kyverno.
- Add configurable Trivy ignore files.
- Add preview mode to show generated files before download or push.
- Add audit logging for full automation actions.

## 26. Summary

This project is a practical DevSecOps bootstrap tool. It turns a small set of application and deployment inputs into a working starter kit that includes CI/CD automation, containerization, Kubernetes deployment manifests, and common security scanning controls.

The generator is especially useful for demos, onboarding new services, standardizing platform templates, and giving teams a consistent secure delivery baseline.

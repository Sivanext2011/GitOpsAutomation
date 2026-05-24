# Automated DevSecOps CI/CD Starter Kit Generator

This project implements the Flask-based generator described in the report. It collects application metadata and produces a downloadable starter kit containing container, CI/CD, Kubernetes, and security scanning artifacts.

For a full project walkthrough, including architecture, routes, generated artifacts, automation flow, security notes, and troubleshooting, see [`PROJECT_DOCUMENTATION.md`](PROJECT_DOCUMENTATION.md).

## Features

- Runtime-aware Dockerfiles for Python, Node.js, Java, and Go
- Jenkins or GitHub Actions pipeline generation
- Trivy dependency and container scanning stages
- Syft SBOM generation stage
- Checkov IaC scanning stage
- Kubernetes Deployment, Service, ConfigMap, Secret example, Ingress, HPA, and NetworkPolicy templates
- ZIP packaging for immediate project onboarding
- Full automation mode that pushes generated code to Git, creates Jenkins credentials, configures a Pipeline job, configures the Jenkins Kubernetes cloud for GKE builds, and optionally starts the build

## Run Locally

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Open `http://127.0.0.1:5000` and generate a starter kit.

## Full Automation Mode

Use **Push and Configure Jenkins** when you want the tool to do the work end to end. The form collects:

- Git repository URL, branch, username, and token
- Jenkins URL, username, API token, and job name
- Docker registry host, username, and password/token
- Kubernetes kubeconfig for VM mode or external-cluster deploys

The app then creates a temporary project, commits the generated files, pushes them to the repository, creates Jenkins credentials, creates or updates the Jenkins Pipeline job, and can trigger the first build. For **GKE / Kubernetes (Kaniko)** builds, it also creates or updates a Jenkins Kubernetes cloud named `kubernetes` so generated `agent { kubernetes { ... } }` pipelines can start agent pods automatically.

Credentials are used during the request and are not written into the generated repository. Jenkins receives the credentials as managed credentials so the pipeline can log in to Docker and deploy with `kubectl`.

Use Docker image prefixes for registry input, not browser URLs. For Docker Hub, use `docker.io/<username>` and a lowercase image name such as `netflixclone`. Use your Docker Hub username and a Docker Hub access token as the Docker registry credentials.

For GKE mode, Jenkins must have the Kubernetes plugin installed and the Jenkins API user must have permission to run Jenkins admin scripts. Jenkins should run with a Kubernetes service account that can create agent pods in its namespace. The automated Kubernetes cloud setup enables WebSocket agents so the generated agent pods can connect back over the Jenkins HTTP(S) endpoint instead of requiring TCP port `50000`.

GKE starter kits also include `jenkins/agent-rbac.yaml`. Apply it once with a cluster-admin kubeconfig if Jenkins reports that its service account cannot list or create pods.

GKE pipelines use runtime-specific tool containers for install and test commands, such as `python:3.12-slim` for Python and `node:22-bookworm-slim` for Node.js. Deployment runs in a separate `alpine:3.20` container, installs `kubectl` during the deploy stage, and creates an in-cluster kubeconfig from the Jenkins agent pod service account token.

Jenkins agents must have these tools available:

```text
git
docker
trivy
syft
checkov
kubectl
```

## Project Layout

```text
app.py
templates/
  index.html
  artifacts/
static/
  styles.css
```

## Security Notes

The generated starter kit uses secure defaults, but production use should connect secrets to a managed secret store, sign container images, enforce cluster admission policies, and tune vulnerability severity gates to match the deployment environment.

# Automated DevSecOps CI/CD Starter Kit Generator

This project implements the Flask-based generator described in the report. It collects application metadata and produces a downloadable starter kit containing container, CI/CD, Kubernetes, and security scanning artifacts.

## Features

- Runtime-aware Dockerfiles for Python, Node.js, Java, and Go
- Jenkins or GitHub Actions pipeline generation
- Trivy dependency and container scanning stages
- Syft SBOM generation stage
- Checkov IaC scanning stage
- Kubernetes Deployment, Service, ConfigMap, Secret example, Ingress, HPA, and NetworkPolicy templates
- ZIP packaging for immediate project onboarding
- Full automation mode that pushes generated code to Git, creates Jenkins credentials, configures a Pipeline job, and optionally starts the build

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
- Kubernetes kubeconfig

The app then creates a temporary project, commits the generated files, pushes them to the repository, creates Jenkins credentials, creates or updates the Jenkins Pipeline job, and can trigger the first build.

Credentials are used during the request and are not written into the generated repository. Jenkins receives the credentials as managed credentials so the pipeline can log in to Docker and deploy with `kubectl`.

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

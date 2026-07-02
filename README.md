# Release Assist MVP

Release Assist is an agentic release engineering assistant MVP that automates release intake, artifact validation, risk assessment, gate decisioning, and deployment scheduling.

It is designed to help AppDev teams submit structured release requests and receive an automated release-readiness assessment through CLI, API, or GitHub Actions. This README also serves as the AppDev onboarding and usage guide for the MVP.

The system supports two main execution modes:

1. **Local execution** using FastAPI and CLI.
2. **Reusable GitHub Actions execution** where consumer repositories call the centralized Release Assist workflow.

---

## 1. Overview

Release Assist validates whether an application release is ready to proceed by running a controlled release pipeline.

The pipeline performs:

1. Release request intake
2. Repository cloning
3. Code quality analysis
4. Vulnerability scanning
5. Dependency mapping
6. LLM-assisted risk assessment with rule-based fallback
7. Change snapshot generation
8. Rule-based gate decision
9. Deployment scheduling
10. PR comment reporting through GitHub Actions

The final output is a structured release assessment containing:

- validation results
- vulnerability findings
- dependency analysis
- risk recommendation
- change snapshot
- gate decision
- scheduling result
- execution logs
- raw JSON output for debugging and auditability

---

## 2. Key Features

### 2.1 Work Intake

Release Assist supports structured release request intake through:

- FastAPI endpoint
- CLI command
- GitHub Actions workflow triggered from PR metadata

Each release request captures:

- application name
- version
- release type
- contact email
- repository URL
- rollback plan
- requested deployment start time
- requested deployment end time
- notification contacts

---

### 2.2 Code Quality Analysis

Release Assist runs code quality checks using **Flake8**.

The quality checker reports:

- quality score
- total issue count
- top violations
- detailed issue list

The quality score is used later by the gate engine to determine release readiness.

---

### 2.3 Vulnerability Scanning

Release Assist uses **Trivy** for filesystem vulnerability scanning.

Trivy is a binary dependency, not a Python package, so it must be installed separately in the reusable workflow before the scan runs.

The vulnerability scanner returns:

- total vulnerability count
- vulnerable package count
- severity counts
- vulnerabilities grouped by:
  - CRITICAL
  - HIGH
  - MEDIUM
  - LOW

---

### 2.4 Dependency Mapping

Release Assist performs dependency analysis using:

- `requirements.txt`
- Python AST import extraction
- previously approved or scheduled release records

It produces:

- upstream dependency map
- downstream dependency map
- dependency version conflicts
- unpinned dependency warnings

This is used to identify whether the current release may affect other services.

---

### 2.5 Risk Assessment

Release Assist performs risk assessment using Gemini when configured.

The LLM generates:

- GO / NO_GO recommendation
- confidence level
- executive summary
- top risks
- suggested fixes
- positive signals

If the LLM is unavailable, times out, or returns invalid JSON, the system falls back to deterministic rule-based assessment.

The LLM is advisory. Final gate decisions are made by deterministic rule-based logic.

---

### 2.6 Change Snapshot

The change snapshot generator records what changed in the release.

It captures:

- total files changed
- added files
- modified files
- deleted files
- renamed files
- configuration changes
- environment variable changes
- schema migration-related changes

For first releases, it generates a first-release snapshot.

---

### 2.7 Rule-Based Gate Decision

The gate engine makes deterministic release decisions based on validation signals.

Possible outcomes:

| Outcome | Meaning |
|---|---|
| `APPROVED` | Release can proceed to scheduling |
| `NEEDS_REVIEW` | Manual review is required |
| `BLOCKED` | Release should not proceed |

The gate engine uses information from:

- quality check
- vulnerability scan
- dependency mapping
- risk assessment
- change snapshot

---

### 2.8 Deployment Scheduler

The scheduler evaluates the requested deployment window.

It checks:

- weekends
- month-end freeze
- year-end freeze
- public holidays
- release gate status

Possible scheduling outcomes:

| Status | Meaning |
|---|---|
| `SCHEDULED` | Requested deployment window is accepted |
| `SUGGESTED_ALTERNATE` | Requested window conflicts with calendar rules and an alternate slot is suggested |
| `BLOCKED` | Release cannot be scheduled |

Important: `SCHEDULED` means the deployment window is accepted. It does not mean the PR has been merged or the application has been deployed.

---

### 2.9 GitHub Actions Integration

Release Assist supports reusable GitHub Actions integration.

Consumer repositories only need a small workflow file that calls the reusable workflow from the central Release Assist repository.

The reusable workflow:

1. Reads the PR description.
2. Validates release metadata.
3. Starts the Release Assist API.
4. Uses the CLI to submit the release request.
5. Runs the full release pipeline.
6. Posts a structured report as a PR comment.

---

## 3. Prerequisites

### 3.1 Local Development Prerequisites

Required:

- Python 3.11 or above
- Git
- pip
- FastAPI dependencies from `requirements.txt`
- Flake8
- Trivy binary
- Gemini API key, if LLM-based risk assessment is required

---

### 3.2 GitHub Actions Prerequisites

Required:

- Consumer repository workflow calling the reusable Release Assist workflow
- PR description following the required YAML schema
- `release` label on the PR
- GitHub Actions permissions for PR comments
- `GEMINI_API_KEY` configured as a secret if LLM mode is required

Required workflow permissions:

```yaml
permissions:
  contents: read
  pull-requests: write
  issues: write
```
---

### 3.3 External Tooling

Release Assist uses both Python dependencies and binary tools.
Python dependencies are installed using:

```shell
pip install -r requirements.txt
```

Binary/tooling dependencies include:
- Git
- Trivy
- jq, if JSON parsing is done in shell scripts

Trivy must be installed separately in the reusable workflow because it is not a Python package.

---

## 4. Repository Structure

Recommended Release Assist repository structure:

```
Release-Assist/
├── app/
│   ├── controllers/
│   │   └── release_controller.py
│   ├── models/
│   │   └── release_model.py
│   ├── routers/
│   │   └── release_router.py
│   └── services/
│       ├── quality_checker.py
│       ├── vulnerability_checker.py
│       ├── dependency_mapper.py
│       ├── risk_reporter.py
│       ├── snapshot_generator.py
│       ├── gate_engine.py
│       └── deployment_scheduler.py
│
├── cli/
│   └── release_agent.py
│
├── data/
│   └── releases.json
│
├── docs/
│   └── evaluation_report.md
│
├── .github/
│   └── workflows/
│       └── release_assist_reusable.yaml
│
├── requirements.txt
└── README.md
```

---

## 5. Environment Variables

Release Assist uses environment variables for runtime configuration.

| Variable | Purpose | Required |
|---|---|---|
| `RELEASE_API_URL` | Base URL for Release Assist API endpoints | Yes |
| `INTERNAL_PATTERNS` | Comma-separated internal service patterns | Yes |
| `GEMINI_API_KEY` | Gemini API key for LLM assessment | Required for LLM mode |
| `GEMINI_MODEL` | Gemini model name | Required for LLM mode |

Example local .env:

```
RELEASE_API_URL=http://127.0.0.1:8000/releases
INTERNAL_PATTERNS=-service,-api,-worker,-client,-gateway
GEMINI_API_KEY=<your-gemini-api-key>
GEMINI_MODEL=<your-preferred-gemini-model>
```

Do not commit .env files or API keys to version control.

---

## 6. Local Setup Instructions

### 6.1 Clone the repository

```shell
git clone https://github.com/UdiptaS24/Release-Assist.git
cd Release-Assist
```

---

### 6.2 Create a virtual environment

Windows:

```shell
python -m venv .venv
.venv\Scripts\activate
```

Linux/macOS:

```shell
python -m venv .venv
source .venv/bin/activate
```

---


### 6.3 Install Python dependencies

```shell
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

---


### 6.4 Install Trivy

Trivy must be installed separately because it is a binary dependency.
In GitHub Actions, the reusable workflow should install Trivy before running the vulnerability scanner.

---


### 6.5 Configure environment

Create a .env file:

```
RELEASE_API_URL=http://127.0.0.1:8000/releases
INTERNAL_PATTERNS=-service,-api,-worker,-client,-gateway
GEMINI_API_KEY=<your-gemini-api-key>
GEMINI_MODEL=<your-preferred-gemini-model>
```

---

## 7. Running Locally

### 7.1 Start the API server

```shell
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

---


### 7.2 Submit a release request

```shell
python cli/release_agent.py submit \
  --app-name payment-service \
  --version 1.1.0 \
  --release-type minor \
  --email payments@example.com \
  --repo-url https://github.com/UdiptaS24/Repo-C.git \
  --rollback-plan "rollback to 1.0.0 if failure" \
  --start "2026-07-02 11:00" \
  --end "2026-07-02 12:00" \
  --notify payments@example.com \
  --notify ops@example.com
```

---


### 7.3 Submit using JSON mode

Use JSON mode for automation:

```shell
python cli/release_agent.py submit \
  --app-name payment-service \
  --version 1.1.0 \
  --release-type minor \
  --email payments@example.com \
  --repo-url https://github.com/UdiptaS24/Repo-C.git \
  --rollback-plan "rollback to 1.0.0 if failure" \
  --start "2026-07-02 11:00" \
  --end "2026-07-02 12:00" \
  --notify payments@example.com \
  --notify ops@example.com \
  --json
```

---


### 7.4 Run the full pipeline

```shell
python cli/release_agent.py run <RELEASE_ID>
```

---


### 7.5 Run the full pipeline in JSON mode

```shell
python cli/release_agent.py run <RELEASE_ID> --json
```

---

## 8. GitHub Actions Integration

Release Assist is intended to be reused from application repositories through a reusable workflow.

The Release Assist core logic remains centralized in the Release-Assist repository.

Consumer repositories only need a small workflow file.

### 8.1 Consumer repository workflow

Create this file in the consumer repository:

```
.github/workflows/release_assist.yaml
```

Example:

```yaml
name: Release Assist Pipeline

on:
  pull_request:
    types: [labeled]

permissions:
  contents: read
  pull-requests: write
  issues: write

jobs:
  release-assist:
    if: contains(github.event.pull_request.labels.*.name, 'release')
    uses: UdiptaS24/Release-Assist/.github/workflows/release_assist_reusable.yaml@main
    secrets:
      GEMINI_API_KEY: ${{ secrets.GEMINI_API_KEY }}
```

---


### 8.2 Triggering the workflow

1. Create a pull request.
2. Add release metadata in the PR description.
3. Add the release label.
4. The reusable workflow runs automatically.
5. The workflow posts a Release Assist report as a PR comment.

---

## 9. PR Description Format

Release Assist reads release metadata from the pull request description.

Use this YAML format:

```yaml
release:
  app_name: payment-service
  version: 1.3.0
  release_type: minor
  contact_email: payments@example.com
  rollback_plan: rollback to 1.2.0 if failure

deployment:
  start: 2026-07-02 11:00
  end: 2026-07-02 12:00

notify:
  - payments@example.com
  - ops@example.com
```

Required fields:

- release.app_name
- release.version
- release.release_type
- release.contact_email
- release.rollback_plan
- deployment.start
- deployment.end
- notify

If required fields are missing or the YAML is malformed, the workflow fails early.

---

## 10. Execution Flow

Github Actions execution flow:

```
Pull request labeled release
        ↓
Reusable workflow starts
        ↓
Required packages and files are installed
        ↓
PR description is parsed and validated
        ↓
Release Assist API starts inside the runner
        ↓
CLI submits release request through API
        ↓
CLI runs full pipeline through API
        ↓
Quality, validation, risk, snapshot, gate and scheduling execute
        ↓
Structured PR comment is posted
```

---

## 11. Architecture and Workflow Overview

Release Assist follows a layered architecture.

```
Consumer Repository PR
        ↓
GitHub Actions Reusable Workflow
        ↓
Release Assist CLI
        ↓
FastAPI API Layer
        ↓
Release Controller
        ↓
Agentic Pipeline Orchestrator
        ↓
Pipeline Steps:
  - clone repository
  - quality check
  - vulnerability scan
  - dependency mapping
  - risk assessment
  - change snapshot
  - rule-based gate decision
  - deployment scheduling
        ↓
Release record storage
        ↓
PR comment output
```

### Agentic Behavior

The system simulates agentic behavior through deterministic orchestration.

It supports:

- sequential execution of tools
- stateful release record updates
- conditional branching
- safe stopping
- retry/fallback handling
- structured decision logs

The LLM is used only for advisory risk assessment. Final gate decisions are rule-based.

---

## 12. Output Interpretation

### 12.1 Pipeline Status

| Status | Meaning |
|---|---|
| `COMPLETED` | Pipeline finished planned steps |
| `STOPPED` | Pipeline stopped due to a hard block |
| `FAILED` | Unexpected failure occurred |

---

### 12.2 Release Status

| Status | Meaning |
|---|---|
| `PENDING` | Release request created but not evaluated |
| `APPROVED` | Release passed gate checks but may not be scheduled yet |
| `NEEDS_REVIEW` | Manual review required |
| `BLOCKED` | Release should not proceed |
| `SCHEDULED` | Requested deployment window accepted |

---

### 12.3 Scheduling Status

| Status | Meaning |
|---|---|
| `SCHEDULED` | Requested deployment window accepted |
| `SUGGESTED_ALTERNATE` | Requested window conflicts with calendar rules |
| `BLOCKED` | Scheduling cannot proceed |

For SUGGESTED_ALTERNATE, update the PR description with the suggested deployment window and re-run the workflow.

Important: SCHEDULED means the deployment window is accepted. The MVP does not perform actual merge or deployment.

---

## 13. MVP Storage Model

For the MVP, data/releases.json acts as a lightweight release registry.

It is used for:

- storing release records
- retrieving previous release versions
- supporting downstream dependency mapping
- maintaining approved or scheduled release history for demo scenarios

Known limitation:

- GitHub-hosted runners are ephemeral.
- File-based storage is not ideal for long-term cross-workflow persistence.
- Production usage should replace this with database-backed persistence.

Current MVP decision:

- maintain seeded release data in data/releases.json
- use it as a lightweight registry
- document database-backed persistence as a future enhancement

---

## 14. Troubleshooting

### GEMINI_API_KEY is missing

Ensure the secret is configured in the consumer repository or organization and passed to the reusable workflow.

### LLM falls back to rule-based assessment

Possible causes:

- missing GEMINI_API_KEY
- missing GEMINI_MODEL
- Gemini API call failure
- invalid Gemini JSON response

The rule-based fallback allows the pipeline to continue safely.

### Trivy not found

Trivy is a binary dependency and must be installed in the reusable workflow.

### PR comment fails with 403

Ensure the workflow has:

```yaml
permissions:
  contents: read
  pull-requests: write
  issues: write
```

Also verify repository Actions settings allow read/write permissions.

### jq parse error

This usually means a file expected to contain JSON contains non-JSON text. Use CLI --json mode for workflow automation.

### RELEASE_ID missing

Ensure submit output is valid JSON and extract:

```shell
jq -r '.id' submit_output.json
```

### Resource not accessible by integration

This usually means the GitHub token does not have permission to create PR comments.

---

## 15. Known MVP Limitations

- Release Assist does not merge PRs.
- Release Assist does not deploy applications.
- SCHEDULED means the deployment window is accepted, not deployed.
- File-based storage is used as MVP persistence.
- Long-term registry should move to a database.
- LLM output is advisory.
- Final gate decision is deterministic and rule-based.
- Organization-level secrets are preferred for scalable multi-repo usage.

---

## 16. Future Enhancements

Potential improvements:

- Replace releases.json with SQLite/PostgreSQL or another persistent registry.
- Add deployment execution simulation.
- Add CI/CD deployment trigger integration.
- Add automatic Git tagging after successful deployment.
- Add dashboard or reporting view.
- Add configurable deployment calendars per application.
- Package Release Assist as an internal platform tool.

---

## 17. Summary

Release Assist provides an MVP implementation of an agentic release engineering assistant.

It validates release requests, analyzes release artifacts, applies deterministic gate logic, evaluates deployment windows, and integrates with GitHub Actions to provide automated PR feedback.

The system prioritizes:

- explainability
- deterministic governance
- reusable workflow integration
- safe fallbacks
- audit-friendly release records
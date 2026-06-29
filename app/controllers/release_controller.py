import os
import json
import subprocess
import tempfile
from datetime import datetime
from app.models.release_model import ReleaseRequest, ReleaseRecord
from app.services.quality_checker import run_quality_check
from app.services.vulnerability_checker import run_vulnerability_scan
from app.services.dependency_mapper import run_dependency_check
from app.services.risk_reporter import generate_risk_report
from app.services.snapshot_generator import generate_change_snapshot
from app.services.gate_engine import apply_gate_logic
from app.services.deployment_scheduler import run_scheduler

STORAGE_FILE = 'data/releases.json'
WORK_DIR_ROOT = 'work'

# auxiliary functions to handle file-based storage of release records
def _load_all_releases() -> list[dict]:
    # Loads all release records from the JSON file and returns as a list of dicts
    if not os.path.exists(STORAGE_FILE):
        return []
    
    with open(STORAGE_FILE, 'r') as f:
        try:
            data = json.load(f)
            return data
        except json.JSONDecodeError:
            return []

def _save_all_releases(releases: list[dict]) -> None:
    # Saves the given list of release records (as dicts) to the JSON file
    os.makedirs(os.path.dirname(STORAGE_FILE), exist_ok=True)
    if not os.path.exists(STORAGE_FILE):
        with open(STORAGE_FILE, 'w') as f:
            json.dump([], f)

    with open(STORAGE_FILE, 'w') as f:
        json.dump(releases, f, indent=4)

def _clone_repository(repo_url: str, target_dir: str) -> dict:
    # Temporarily clones the repository into target_dir and return {"success": bool, "error": str}
    try:
        result = subprocess.run(["git", "clone", "--depth", "1", repo_url, target_dir], capture_output=True, text=True, timeout=240)
        if result.returncode != 0:
            return {"success": False, "error": result.stderr.strip()}
        return {"success": True, "error": None}
    except FileNotFoundError:
        return {"success": False, "error": "Git is not installed or not found in PATH."}
    except Exception as e:
        return {"success": False, "error": str(e)}


def _get_deployed_services() -> list[dict]:
    return [r for r in _load_all_releases() if r["status"] in ("APPROVED", "SCHEDULED")]

def _get_previous_version(app_name: str, current_version: str) -> str | None:
    prior = [r for r in _load_all_releases()
             if r["app_name"].lower() == app_name.lower()
             and r["version"] != current_version
             and r["status"] in ("APPROVED", "SCHEDULED")]
    if not prior:
        return None
    prior.sort(key=lambda r: r["created_at"], reverse=True)
    return prior[0]["version"]

def _run_validation(record: ReleaseRecord):
    # Runs validations such as code quality check, vulnerability check
    repo_url = record.repository_url
    with tempfile.TemporaryDirectory() as temp_dir:
        clone_result = _clone_repository(repo_url, temp_dir)
        if not clone_result["success"]:
            record.validation_report["error"] = f"Failed to clone repository: {clone_result["error"]}"
            return
        record.validation_report["quality_check"] = run_quality_check(temp_dir)
        record.validation_report["vulnerability_scan"] = run_vulnerability_scan(temp_dir)
        record.validation_report["dependencies"] = run_dependency_check(temp_dir, record.app_name, _get_deployed_services())
        prev_version = _get_previous_version(record.app_name, record.version)
        record.change_snapshot = generate_change_snapshot(temp_dir, record.version, prev_version)
        record.validation_report["risk_report"] = generate_risk_report(record.validation_report, record.app_name, record.version)
        record.validation_report["gate_decision"] = apply_gate_logic(record.validation_report, record.change_snapshot)
        record.status = record.validation_report["gate_decision"]["outcome"]

def store_release_record(new_release_request: ReleaseRequest) -> dict:    
    # Stores a new release record based on the incoming ReleaseRequest, runs code quality check and returns the stored record as dict
    data = _load_all_releases()
    new_release_record = ReleaseRecord(**new_release_request.model_dump())
    new_release_record.repository_url = str(new_release_record.repository_url)
    record_dict = new_release_record.model_dump(mode="json")
    data.append(record_dict)
    _save_all_releases(data)
    return record_dict

def get_all_releases() -> list[dict]:
    # Returns a list of all release records as dicts
    return _load_all_releases()

def get_release_by_id(release_id: str) -> dict | None:
    # Returns a specific release record as dict
    data = _load_all_releases()
    for record in data:
        if record['id'] == release_id:
            return record
    return None

def schedule_release(release_id: str, requested_start: datetime, requested_end: datetime, notify_contacts: list[str] | None = None) -> dict | None:
    data = _load_all_releases()
    for record in data:
        if record["id"] == release_id:
            record["requested_start"] = requested_start
            record["requested_end"] = requested_end
            record["notify_contacts"] = notify_contacts or []
            schedule_result = run_scheduler(record)
            record["schedule"] = schedule_result
            _save_all_releases(data)
            return record
    return None

# ==========AGENTIC PIPELINE ORCHESTRATOR==========
MAX_CLONE_RETRIES = 3

LEGAL_TRANSITIONS = {
    "PENDING": {"APPROVED", "NEEDS_REVIEW", "BLOCKED"},
    "APPROVED": {"SCHEDULED"},
    "NEEDS_REVIEW": {"APPROVED", "BLOCKED"},
    "BLOCKED": {"APPROVED"},
    "SCHEDULED": set()
}

class PipelineHardBlock(Exception):
    """Raised when the agent must stop the pipeline safely."""

def _log_step(record: dict, step: str, status: str, message: str = ""):
    record.setdefault("pipeline_log", []).append({
        "step": step,
        "status": status,
        "message": message,
    })


def _transition_status(record: dict, new_status: str):
    current = record.get("status", "PENDING")
    if current == new_status:
        return
 
    if new_status not in LEGAL_TRANSITIONS.get(current, set()):
        raise PipelineHardBlock(
            f"Illegal status transition: {current} -> {new_status}"
        )
    record["status"] = new_status


def _step_clone(record: dict, target_dir: str) -> str:
    repo_url = record["repository_url"]

    for attempt in range(1, MAX_CLONE_RETRIES + 1):
        clone_result = _clone_repository(repo_url, target_dir)

        if clone_result["success"]:
            _log_step(record, "clone", "success",
                      f"Cloned on attempt {attempt}")
            return

        if attempt == MAX_CLONE_RETRIES:
            record["validation_report"]["error"] = (
                f"Failed to clone repository after {attempt} attempts: "
                f"{clone_result['error']}"
            )
            _log_step(record, "clone", "failed", clone_result["error"])
            raise PipelineHardBlock("Clone failed after max retries.")


def _step_quality(record: dict, repo_dir: str):
    result = run_quality_check(repo_dir)
    record["validation_report"]["quality_check"] = result
    step_status = result.get("status", "unknown")
    message = result.get("message", "") if step_status == "error" else ""
    _log_step(record, "quality_check", step_status, message)


def _step_vulnerabilities(record: dict, repo_dir: str):
    result = run_vulnerability_scan(repo_dir)
    record["validation_report"]["vulnerability_scan"] = result
    step_status = result.get("status", "unknown")
    message = result.get("error", "") if step_status == "error" else ""
    _log_step(record, "vulnerability_scan", step_status, message)


def _step_dependencies(record: dict, repo_dir: str):
    result = run_dependency_check(
        repo_dir,
        record["app_name"],
        _get_deployed_services(),
    )
    record["validation_report"]["dependencies"] = result
    step_status = result.get("status", "unknown")
    message = result.get("reason", "") if step_status == "error" else ""
    _log_step(record, "dependency_check", step_status, message)


def _step_risk(record: dict):
    result = generate_risk_report(
        record["validation_report"], record["app_name"], record["version"]
    )
    record["validation_report"]["risk_report"] = result
    step_status = result.get("status", "unknown")
    message = result.get("message", "") if step_status == "error" else ""
    _log_step(record, "risk_report", step_status, message)


def _step_snapshot(record: dict, repo_dir: str):
    previous_version = _get_previous_version(
        record["app_name"], record["version"]
    )
    snapshot = generate_change_snapshot(
        repo_dir, record["version"], previous_version
    )
    record["change_snapshot"] = snapshot    
    step_status = snapshot.get("status", "unknown")
    message = ""
    if step_status == "skipped":
        message = snapshot.get("reason", "Snapshot skipped")
    elif step_status == "error":
        message = snapshot.get("message", "")
    _log_step(record, "change_snapshot", step_status, message)


def _step_gate(record: dict):
    decision = apply_gate_logic(
        record["validation_report"], record["change_snapshot"]
    )
    record["validation_report"]["gate_decision"] = decision
    new_status = decision.get("outcome", "NEEDS_REVIEW")
    _transition_status(record, new_status)
    _log_step(record, "gate_decision", new_status, decision.get("reason", ""))


def _step_schedule(record: dict):
    if record["status"] != "APPROVED":
        _log_step(record, "scheduler", "skipped",
                  f"Not eligible: status={record['status']}")
        return

    schedule_result = run_scheduler(record)
    record["schedule"] = schedule_result

    if schedule_result["status"] == "SCHEDULED":
        _transition_status(record, "SCHEDULED")
        _log_step(record, "scheduler", "scheduled",
                  schedule_result["reason"])
    else:
        _log_step(record, "scheduler", schedule_result["status"].lower(),
                  schedule_result["reason"])


def run_pipeline(release_id: str) -> dict | None:
    data = _load_all_releases()
    record = next((r for r in data if r["id"] == release_id), None)

    if not record:
        return None

    record.setdefault("validation_report", {})
    record.setdefault("change_snapshot", {})
    record["pipeline_log"] = []
    record["pipeline_status"] = "RUNNING"
    if record["status"] in ("NEEDS_REVIEW", "BLOCKED"):
        record["status"] = "PENDING"

    try:
        with tempfile.TemporaryDirectory() as repo_dir:
            _step_clone(record, repo_dir)
            _step_quality(record, repo_dir)
            _step_vulnerabilities(record, repo_dir)
            _step_dependencies(record, repo_dir)
            _step_risk(record)
            _step_snapshot(record, repo_dir)
            _step_gate(record)
            _step_schedule(record)
            record["pipeline_status"] = "COMPLETED"

    except PipelineHardBlock as block:
        record["pipeline_status"] = "STOPPED"
        record["pipeline_log"].append({
            "step": "agent",
            "status": "hard_block",
            "message": str(block),
        })

    except Exception as exc:
        record["pipeline_status"] = "FAILED"
        record["pipeline_log"].append({
            "step": "agent",
            "status": "error",
            "message": str(exc),
        })

    for i, existing in enumerate(data):
        if existing["id"] == release_id:
            data[i] = record
            break

    _save_all_releases(data)
    return record
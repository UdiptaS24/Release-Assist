import os
import json
import uuid
import shutil
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
    _run_validation(new_release_record)
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

def update_release_status(release_id: str, new_status: str) -> dict | None:
    # Updates the status of a specific release record
    data = _load_all_releases()
    for record in data:
        if record['id'] == release_id:
            record['status'] = new_status
            _save_all_releases(data)
            return record
    return None

def schedule_release(release_id: str, requested_start: datetime, requested_end: datetime, notify_contacts: list[str] | None = None) -> dict | None:
    data = _load_all_releases()
    for record in data:
        if record["id"] == release_id:
            schedule_result = run_scheduler(record, requested_start, requested_end, notify_contacts or [])
            record["schedule"] = schedule_result
            _save_all_releases(data)
            return record
    return None
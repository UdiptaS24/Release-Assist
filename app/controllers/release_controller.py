import os
import json
from app.models.release_model import ReleaseRequest, ReleaseRecord
from app.services.quality_checker import run_quality_check

STORAGE_FILE = 'data/releases.json'

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

def store_release_record(new_release_request: ReleaseRequest) -> dict:    
    # Stores a new release record based on the incoming ReleaseRequest, runs code quality check and returns the stored record as dict
    data = _load_all_releases()
    new_release_record = ReleaseRecord(**new_release_request.model_dump())
    new_release_record.repository_url = str(new_release_record.repository_url)
    quality_check_result = run_quality_check(new_release_record.repository_url)
    new_release_record.validation_report["quality_check"] = quality_check_result
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
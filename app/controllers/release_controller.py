import os
import json
from app.models.release_model import ReleaseRequest, ReleaseRecord

STORAGE_FILE = 'data/releases.json'

# auxiliary functions to handle file-based storage of release records
def _load_all_releases() -> list[dict]:
    if not os.path.exists(STORAGE_FILE):
        return []
    
    with open(STORAGE_FILE, 'r') as f:
        try:
            data = json.load(f)
            return data
        except json.JSONDecodeError:
            return []

def _save_all_releases(releases: list[dict]) -> None:
    os.makedirs(os.path.dirname(STORAGE_FILE), exist_ok=True)
    if not os.path.exists(STORAGE_FILE):
        with open(STORAGE_FILE, 'w') as f:
            json.dump([], f)

    with open(STORAGE_FILE, 'w') as f:
        json.dump(releases, f, indent=4)

def store_release_record(new_release_request: ReleaseRequest) -> dict:    
    data = _load_all_releases()
    new_release_record = ReleaseRecord(**new_release_request.model_dump())
    record_dict = new_release_record.model_dump(mode="json")
    data.append(record_dict)
    _save_all_releases(data)
    return record_dict

def get_all_releases() -> list[dict]:
    return _load_all_releases()

def get_release_by_id(release_id: str) -> dict | None:
    data = _load_all_releases()
    for record in data:
        if record['id'] == release_id:
            return record
    return None

def update_release_status(release_id: str, new_status: str) -> dict | None:
    data = _load_all_releases()
    for record in data:
        if record['id'] == release_id:
            record['status'] = new_status
            _save_all_releases(data)
            return record
    return None
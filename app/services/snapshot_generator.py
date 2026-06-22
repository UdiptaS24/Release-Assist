import os
import re
import subprocess

GIT_STATUS_MAP = {
    "A": "added",
    "M": "modified",
    "D": "deleted",
    "R": "renamed",
    "C": "copied"
}

MIGRATION_PATTERS = ["migration", "alembic", "migrate", ".sql", "schema"]
CONFIG_EXTENSIONS = (".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf")
ENV_FILE_NAMES = (".env", ".env.example", ".env.sample")

def run_git(command: list, target_dir: str) -> tuple[str, bool]:
    result = subprocess.run(command, cwd=target_dir, capture_output=True, text=True)
    return result.stdout.strip(), result.returncode == 0


def resolve_version_ref(target_dir: str, version: str) -> str | None:
    for candidate in (version, f"v{version}"):
        _, success = run_git(["git", "rev-parse", "--verify", candidate], target_dir)
        if success:
            return candidate
    return None

def parse_changed_files(name_status_output: str) -> tuple[list, list, list]:
    files_changed = []
    schema_migrations = []
    config_deltas = []

    for line in name_status_output.splitlines():
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            continue

        status_code = parts[0][0]
        filepath = parts[-1]
        status = GIT_STATUS_MAP.get(status_code, "unknown")

        files_changed.append({"status": status, "file": filepath})

        if any(p in filepath.lower() for p in MIGRATION_PATTERS):
            schema_migrations.append({"status": status, "file": filepath})

        base = os.path.basename(filepath)
        if filepath.endswith(CONFIG_EXTENSIONS) or base in ENV_FILE_NAMES:
            config_deltas.append({"status": status, "file": filepath})

    return files_changed, schema_migrations, config_deltas

def extract_env_variables(raw_diff: str) -> dict:
    added = set()
    removed = set()

    env_file_added   = re.compile(r'^\+(?!\+\+)\s*([A-Z_][A-Z0-9_]*)=')
    env_file_removed = re.compile(r'^-(?!--)\s*([A-Z_][A-Z0-9_]*)=')

    code_pattern = re.compile(r'os\.(?:environ(?:\.get)?\[[\'\"]([\w]+)[\'\"]\]|getenv\([\'\"]([\w]+)[\'\"]\))')

    for line in raw_diff.splitlines():
        if line.startswith("+") and not line.startswith("+++"):
            match = env_file_added.match(line)
            if match:
                added.add(match.group(1))
            for m in code_pattern.finditer(line):
                added.add(m.group(1) or m.group(2))
        elif line.startswith("-") and not line.startswith("---"):
            match = env_file_removed.match(line)
            if match:
                removed.add(match.group(1))
            for m in code_pattern.finditer(line):
                removed.add(m.group(1) or m.group(2))
    return{
        "added": sorted(added - removed),
        "removed": sorted(removed - added)
    }

def build_first_release_snapshot(target_dir: str, current_version: str) -> dict:
    all_tracked, _ = run_git(["git", "ls-files"], target_dir)
    tracked_files = [f for f in all_tracked.splitlines() if f]

    files_changed = []
    schema_migrations = []
    config_deltas = []

    for filepath in tracked_files:
        files_changed.append({"status": "added", "file": filepath})
        if any(p in filepath.lower() for p in MIGRATION_PATTERS):
            schema_migrations.append({"status": "added", "file": filepath})

        base = os.path.basename(filepath)
        if filepath.endswith(CONFIG_EXTENSIONS) or base in ENV_FILE_NAMES:
            config_deltas.append({"status": "added", "file": filepath})
    
    return {
        "status": "success",
        "is_first_release": True,
        "current_version": current_version,
        "previous_version": None,
        "summary": {
            "total_files_changed": len(files_changed),
            "added": len(files_changed),
            "modified": 0,
            "deleted": 0,
            "renamed": 0
        },
        "files": files_changed,
        "schema_migrations_detected": schema_migrations,
        "config_files_modified": config_deltas,
        "new_env_vars_detected": {"added": [], "removed": []}
    }

def generate_change_snapshot(target_dir: str, current_version: str, previous_version: str | None = None) -> dict:
    if not previous_version:
        return build_first_release_snapshot(target_dir, current_version)
    
    run_git(["git", "fetch", "--unshallow", "--tags"], target_dir)
    run_git(["git", "fetch", "--tags"], target_dir)
    
    resolved_ref = resolve_version_ref(target_dir, previous_version)
    if not resolved_ref:
        return {
            "status": "skipped",
            "reason": (
                f"Could not resolve git tag for previous version '{previous_version}'."
                f"Tried '{previous_version}' and 'v{previous_version}'."
                f"Ensure the tag exists in the repository."
            ),
            "current_version": current_version,
            "previous_version": previous_version
        }
    
    name_status_output, success = run_git(["git", "diff", "--name-status", resolved_ref, "HEAD"], target_dir)
    if not success:
        
        return {
            "status": "skipped",
            "reason": f"git diff failed between '{resolved_ref}' and HEAD.",
            "current_version": current_version,
            "previous_version": previous_version
        }

    if not name_status_output:
        return {
            "status": "skipped",
            "reason": "No differences found between versions — possible duplicate submission.",
            "current_version": current_version,
            "previous_version": previous_version
        }
    files_changed, schema_migrations, config_deltas = parse_changed_files(name_status_output)
    raw_diff, _ = run_git(["git", "diff", resolved_ref, "HEAD"], target_dir)
    env_vars = extract_env_variables(raw_diff)

    counts = {"added": 0, "modified": 0, "deleted": 0, "renamed": 0}
    for f in files_changed:
        if f["status"] in counts:
            counts[f["status"]] += 1
    
    
    return {
        "status": "completed",
        "is_first_release": False,
        "current_version": current_version,
        "previous_version": previous_version,
        "resolved_previous_ref": resolved_ref,
        "summary": {
            "total_files_changed": len(files_changed),
            **counts
        },
        "files": files_changed,
        "schema_migrations_detected": schema_migrations,
        "config_files_modified": config_deltas,
        "new_env_vars_detected": env_vars
    }

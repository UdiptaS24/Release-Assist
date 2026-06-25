import os
import ast
import re
from dotenv import load_dotenv

load_dotenv()

REQ_PATTERN = re.compile(r'^([a-zA-Z0-9\-_.]+)(?:\[[\w,\s-]+\])?(.*?)$')
SPECIFIER_PATTERN = re.compile(r'(==|!=|~=|>=|<=|>|<)\s*([\d]+\.[\d]+(?:\.[\d]+)?(?:\.[\d]+)?)')
INTERNAL_SERVICE_PATTERNS = os.getenv("INTERNAL_PATTERNS").split(',')

def normalise_package_name(package_name: str) -> str:
    return package_name.lower().replace("_", "-").replace(".", "-")

def extract_actual_imports(repo_dir: str) -> set:
    imports = set()
    for root, _, files in os.walk(repo_dir):
        for file in files:
            if not file.endswith(".py"):
                continue
            try:
                with open(os.path.join(root, file), "r", encoding="utf-8", errors="ignore") as f:
                    tree = ast.parse(f.read())
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            imports.add(alias.name.split('.')[0])
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            imports.add(node.module.split(".")[0])
            except Exception as e:
                continue
    return {normalise_package_name(package) for package in imports}

def extract_declared_requirements(repo_dir: str) -> dict:
    req_file = os.path.join(repo_dir, "requirements.txt")
    requirements = {}
    if not os.path.exists(req_file):
        return requirements
    
    with open(req_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.split("#")[0].strip()
            if not line or line.startswith("-"):
                continue
            match = REQ_PATTERN.match(line)
            if match:
                package_name = normalise_package_name(match.group(1))
                version_spec = match.group(2).strip() or None
                requirements[package_name] = version_spec
    
    return requirements

def parse_version(version_str: str) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in version_str.strip().split("."))
    except ValueError:
        return (0,)
    
def check_specifier(operator: str, production: tuple, required: tuple) -> bool:
    if operator == "==":
        return production == required
    if operator == "!=":
        return production != required
    if operator == ">=":
        return production >= required
    if operator == "<=":
        return production <= required
    if operator == ">":
        return production > required
    if operator == "<":
        return production < required
    if operator == "~=":
        if len(required) < 2:
            return production >= required
        prefix = required[:-1]
        return production >= required and production[:len(prefix)] == prefix
    return True

def get_severity_and_explanation(operator: str, required_specifier: str, production_version: str) -> tuple[str, str]:
    if operator in ("==", "!=", "~="):
        severity = "ERROR"
        if operator == "==":
            explanation = (
                f"Exact pin mismatch, production is running v{production_version} "
                f"but this release strictly requires {required_specifier}. "
                f"Will likely cause runtime errors."
            )
        elif operator == "!=":
            explanation = (
                f"Production version v{production_version} is explicitly excluded "
                f"by {required_specifier}. Incompatible deployment."
            )
        else:
            explanation = (
                f"Production v{production_version} falls outside the compatible "
                f"release range {required_specifier}. "
                f"~= only allows the last specified component to vary."
            )
    else:
        severity = "WARNING"
        if operator in (">", ">="):
            explanation = (
                f"Production v{production_version} is behind the minimum required "
                f"version {required_specifier}. "
                f"May require a coordinated upgrade of the upstream service."
            )
        else:
            explanation = (
                f"Production v{production_version} exceeds the maximum allowed "
                f"version {required_specifier}. "
                f"A newer production version may have breaking changes."
            )
    return severity, explanation

def detect_version_conflicts(package_name: str, required_specifier: str, production_version: str) -> dict | None:
    production_tuple = parse_version(production_version)
    specifiers = SPECIFIER_PATTERN.findall(required_specifier)

    if not specifiers:
        return None
    
    for operator, version_str in specifiers:
        required_tuple = parse_version(version_str)
        satisfied = check_specifier(operator, production_tuple, required_tuple)
        if not satisfied:
            severity, explanation = get_severity_and_explanation(operator, required_specifier, production_version)
            return {
                "type": "VERSION_CONFLICT",
                "service": package_name,
                "severity": severity,
                "required": required_specifier,
                "production_version": production_version,
                "message": f"Requires {required_specifier} but production is running v{production_version}",
                "explanation": explanation
            }
    return None

def detect_unpinned_dependencies(declared_requirements: dict) -> list[dict]:
    warnings = []
    for package_name, specifier in declared_requirements.items():
        if not specifier:
            warnings.append({
                "type": "UNPINNED_DEPENDENCY",
                "service": package_name,
                "severity": "WARNING",
                "message": f"'{package_name}' has no version constraint.",
                "explanation": (
                    f"Unpinned dependencies can break builds when upstream releases a new major version"
                    f"Pin to at least >=X.Y, <X+1"
                )
            })
    return warnings

def build_upstream_map(declared_requirements: dict, actual_imports: set, production_registry: dict) -> tuple[list, list]:
    upstream_map = []
    conflicts = []

    all_packages = set(declared_requirements.keys()) | actual_imports

    for package_name in all_packages:
        if package_name not in production_registry:
            if any(package_name.endswith(p) for p in INTERNAL_SERVICE_PATTERNS):
                conflicts.append({
                    "type": "MISSING_PEER",
                    "service": package_name,
                    "severity": "WARNING",
                    "message": f"'{package_name}' looks like an internal service but is not in production.",
                    "explanation": "May be a new undeployed service or a naming mismatch."
                })
            
            else:
                upstream_map.append({
                    "service": package_name,
                    "required": declared_requirements.get(package_name, "UNSPECIFIED"),
                    "currently_deployed": "EXTERNAL",
                })

            continue
        
        required_version = declared_requirements.get(package_name, "UNSPECIFIED")
        production_version = production_registry[package_name]

        upstream_map.append({
            "service": package_name,
            "required" : required_version,
            "currently_deployed": production_version
        })

        if required_version and required_version != "UNSPECIFIED":
            detected_conflicts = detect_version_conflicts(package_name, required_version, production_version)
            if detected_conflicts:
                conflicts.append(detected_conflicts)
    return upstream_map, conflicts

def build_downstream_map(app_name: str, deployed_services: list[dict]) -> list[dict]:
    downstream_map = []
    normalised_app_name = normalise_package_name(app_name)
    for service in deployed_services:
        past_upstream = (
            service.get("validation_report", {})
                   .get("dependencies", {})
                   .get("upstream", {})
                   .get("packages", [])
        )
        for package in past_upstream:
            if normalise_package_name(package.get("service")) == normalised_app_name: 
                downstream_map.append({
                    "service": service["app_name"],
                    "version": service["version"],
                    "required_version": package.get("required", "UNSPECIFIED") 
                })
                break
    return downstream_map

def run_dependency_check(repo_dir: str, app_name: str, deployed_services: list[dict]) -> dict:
    declared_requirements = extract_declared_requirements(repo_dir)
    if not declared_requirements:
        return{"status": "error", "reason": "No requirements.txt file found"}
    actual_imports = extract_actual_imports(repo_dir)

    production_registry = {normalise_package_name(s["app_name"]) : s["version"] 
                           for s in sorted(deployed_services, key=lambda x: x["created_at"])}

    upstream_map, version_conflicts = build_upstream_map(declared_requirements, actual_imports, production_registry)

    unpinned_warnings = detect_unpinned_dependencies(declared_requirements)

    downstream_map = build_downstream_map(app_name, deployed_services)

    all_flags = version_conflicts + unpinned_warnings
    error_count = sum(1 for flag in all_flags if flag["severity"] == "ERROR")
    warning_count = sum(1 for flag in all_flags if flag["severity"] == "WARNING")
    return {
        "status" : "success",
        "upstream" : {
            "total": len(upstream_map),
            "packages": upstream_map
        },
        "downstream": {
            "total": len(downstream_map),
            "services": downstream_map
        },
        "flags": {
            "errors": error_count,
            "warnings": warning_count,
            "details": all_flags
        }
    }
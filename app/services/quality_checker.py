import re
import subprocess
from collections import Counter

FLAKE8_LINE_PATTERN = re.compile(r'^(?P<file>.+?):(?P<line>\d+):(?P<col>\d+): (?P<code>\w\d+) (?P<message>.+)$')
    
def run_flake8(repo_path: str) -> str:
    # Runs flake8 on the target_dir and returns the raw stdout
    try:
        result = subprocess.run(["flake8", repo_path, "--format=default"], capture_output=True, text=True, timeout=120)
        return result.stdout
    except FileNotFoundError:
        return "Error: flake8 is not installed or not found in PATH."
    except subprocess.TimeoutExpired:
        return "Error: flake8 execution timed out after 120 seconds."
    except Exception as e:
        return f"Error running flake8: {str(e)}"

def parse_flake8_output(raw_output: str, repo_path: str) -> dict:
    # Parses the raw flake8 output and returns a structured summary dict
    issues = []
    for line in raw_output.strip().splitlines():
        match = FLAKE8_LINE_PATTERN.match(line)
        if not match:
            continue
        file_path = match.group("file").replace(repo_path, "").lstrip("/\\")
        issues.append({
            "file": file_path,
            "line": int(match.group("line")),
            "col": int(match.group("col")),
            "code": match.group("code"),
            "message": match.group("message")
        })

    total_issues = len(issues)
    quality_score = max(0, 100 - total_issues * 2)
    issue_code_counts = Counter(issue["code"] for issue in issues)
    top_violations = [{"code": code, "count": count} for code, count in issue_code_counts.most_common(5)]

    return {
        "quality_score": quality_score,
        "total_issues": total_issues,
        "top_violations": top_violations,
        "issues": issues
    }
    
def run_quality_check(repo_path: str) -> dict:
    # Main function to run the quality check
    raw_flake8_output = run_flake8(repo_path)
    if raw_flake8_output.startswith("Error:"):
        return {"status" : "error", "message": raw_flake8_output}
    parsed_result = parse_flake8_output(raw_flake8_output, repo_path)
    parsed_result["status"] = "success"
    return parsed_result
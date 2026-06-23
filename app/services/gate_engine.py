def extract_metrics(validation_report: dict) -> dict:
    qc = validation_report.get("quality_check", {})
    vs = validation_report.get("vulnerability_scan", {})
    dep = validation_report.get("dependencies", {})
    llm = validation_report.get("risk_report", {}).get("assessment", {})

    return {
        "quality_status": qc.get("status"),
        "quality_score": qc.get("quality_score", 100),
        "total_issues": qc.get("total_issues", 0),

        "vulns_status": vs.get("status"),
        "critical_vulns": vs.get("severity_counts", {}).get("CRITICAL", 0),
        "high_vulns": vs.get("severity_counts", {}).get("HIGH", 0),
        "medium_vulns": vs.get("severity_counts", {}).get("MEDIUM", 0),
        "low_vulns": vs.get("severity_counts", {}).get("LOW", 0),

        "dep_status": dep.get("status"),
        "dep_errors": dep.get("flags", {}).get("errors", 0),
        "dep_warnings": dep.get("flags", {}).get("warnings", 0),
        "upstream_total": dep.get("upstream", {}).get("total", 0),
        "downstream_total": dep.get("downstream", {}).get("total", 0),

        "llm_recommendation": llm.get("recommendation"),
        "llm_confidence": llm.get("confidence")
    }

def check_block_conditions(m: dict) -> list[str]:
    reasons = []
    if m["critical_vulns"] > 0:
        reasons.append(f"{m['critical_vulns']} CRITICAL {'vulnerability' if m['critical_vulns'] == 1 else 'vulnerabilities'} detected")
    if m["dep_errors"] > 0:
        reasons.append(f"{m['dep_errors']} dependency {'error' if m['dep_errors'] == 1 else 'errors'} detected")
    if m["quality_score"] < 50:
        reasons.append(f"Quality score too low ({m['quality_score']}/100)")
    if m["total_issues"] > 50:
        reasons.append(f"Too many lint issues ({m['total_issues']})")
    return reasons
    
def check_review_conditions(m: dict) -> list[str]:
    reasons = []
    if m["quality_status"] == "error":
        reasons.append("Quality check failed to complete.")
    if m["vulns_status"] == "error":
        reasons.append("Vulnerability scan failed to complete")
    if m["dep_status"] == "error":
        reasons.append("Dependency mapping failed to complete.")
    if m["high_vulns"] > 0:
        reasons.append(f"{m['high_vulns']} HIGH {'vulnerability' if m['high_vulns'] == 1 else 'vulnerabilities'} detected")
    if m["quality_score"] < 70:
        reasons.append(f"Quality score below threshold ({m['quality_score']})")
    if m["dep_warnings"] > 0:
        reasons.append(f"{m['dep_warnings']} dependency {'warning' if m['dep_warnings'] == 1 else 'warnings'} detected")
    if m["total_issues"] > 20:
        reasons.append(f"{m['total_issues']} lint issues detected")
    return reasons

def check_snapshot_conditions(snapshot: dict | None) -> list[str]:
    if not snapshot:
        return []
    reasons = []
    migrations = snapshot.get("schema_migrations_detected", [])
    if len(migrations) > 0:
        reasons.append("Schema migrations detected (DBA review required)")
    return reasons

def decide_status(block_reasons: list[str], review_reasons: list[str]) -> tuple[str, str, str]:
    if block_reasons:
        return ("BLOCKED", block_reasons[0], "ERROR")
    if review_reasons:
        return ("NEEDS_REVIEW", review_reasons[0], "WARNING")
    return ("APPROVED", "All automated checks passed successfully", "INFO")

def apply_gate_logic(validation_report: dict, change_snapshot: dict | None = None) -> dict:
    metrics = extract_metrics(validation_report)

    block_reasons = check_block_conditions(metrics)
    review_reasons = check_review_conditions(metrics) + check_snapshot_conditions(change_snapshot)

    status, primary_reason, severity = decide_status(block_reasons, review_reasons)

    llm_note = None;
    llm_rec = metrics["llm_recommendation"]
    if llm_rec:
        mapped_llm_rec = "BLOCKED" if llm_rec == "NO_GO" else "APPROVED"
        if mapped_llm_rec != status:
            llm_note = f"LLM recommended {llm_rec}, but rule engine decided {status}"
    return{
        "outcome": status,
        "decision_source": "rule_engine",
        "reason": primary_reason, 
        "severity": severity, 
        "contributing_factors": block_reasons + review_reasons,
        "metrics": metrics,
        "llm_advisory": {
            "recommendation": metrics["llm_recommendation"],
            "confidence": metrics["llm_confidence"],
            "note": llm_note
        },
        "auto_decided": True
    }
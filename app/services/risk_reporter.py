import os
import json
from google import genai
# from google.genai import types
from  dotenv import load_dotenv

load_dotenv()

SYSTEM_PROMPT = """
You are a senior DevOps release engineer reviewing a software release.
You receive a JSON validation report with three sections:
  - quality_check: Flake8 results (quality_score 0-100, total_issues, top_violations, issues)
  - vulnerability_scan: Trivy CVE findings bucketed by CRITICAL / HIGH / MEDIUM / LOW
  - dependencies: upstream packages, downstream services, and flagged conflicts/warnings

Your job is to produce a JSON risk assessment with this exact shape:
{
  "recommendation": "GO" | "NO_GO",
  "confidence": "HIGH" | "MEDIUM" | "LOW",
  "summary": "2-3 sentence executive summary",
  "top_risks": [
    {
      "title": "concise risk title",
      "severity": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW",
      "category": "QUALITY" | "VULNERABILITY" | "DEPENDENCY",
      "description": "plain-English explanation",
      "suggested_fix": "specific actionable remediation"
    }
  ],
  "positive_signals": ["string", ...]
}

Decision rules (binary — only GO or NO_GO):
- NO_GO if ANY of these are true:
    * One or more CRITICAL vulnerabilities exist
    * One or more HIGH vulnerabilities exist
    * dependencies.flags has any ERROR severity item
    * quality_score < 70
- GO otherwise (even if MEDIUM/LOW vulnerabilities or WARNING flags exist — flag them as risks but still GO)

Before producing JSON, internally reason through:
- Are there any CRITICAL or HIGH vulnerabilities or ERROR dependency flags?
- What is the quality_score and how does it compare to the threshold?
- Are there downstream services that will be impacted?
Then output ONLY the final JSON. No preamble, no explanation outside JSON.

Rules:
- top_risks must have AT MOST 3 items, sorted by severity (CRITICAL first, then HIGH, MEDIUM, LOW)
- Even GO releases can list risks worth noting (e.g., MEDIUM vulns, unpinned deps, downstream impacts)
- suggested_fix must be specific (e.g., "Upgrade jinja2 to 3.1.3 in requirements.txt")
- Be factual and concise. No marketing fluff.
- Always return valid JSON. Nothing else.
"""

FEW_SHOT_EXAMPLES = [
    # Example 1: Clean release → GO
    {
        "user": json.dumps({
            "app_name": "billing-service",
            "version": "1.2.0",
            "validation_report": {
                "quality_check": {
                    "status": "success",
                    "quality_score": 94,
                    "total_issues": 3,
                    "top_violations": [
                        {"code": "E501", "count": 2},
                        {"code": "W291", "count": 1}
                    ],
                    "issues": [
                        {"file": "app/main.py", "line": 12, "col": 80, "code": "E501",
                         "message": "line too long (88 > 79 characters)"},
                        {"file": "app/main.py", "line": 45, "col": 80, "code": "E501",
                         "message": "line too long (90 > 79 characters)"},
                        {"file": "app/utils.py", "line": 7, "col": 30, "code": "W291",
                         "message": "trailing whitespace"}
                    ]
                },
                "vulnerability_scan": {
                    "CRITICAL": [],
                    "HIGH": [],
                    "MEDIUM": [],
                    "LOW": []
                },
                "dependencies": {
                    "status": "success",
                    "upstream": {
                        "total": 3,
                        "packages": [
                            {"service": "fastapi", "required": ">=0.100.0", "currently_deployed": "EXTERNAL"},
                            {"service": "uvicorn", "required": ">=0.20.0", "currently_deployed": "EXTERNAL"},
                            {"service": "payment-service", "required": ">=1.0.0", "currently_deployed": "1.0.0"}
                        ]
                    },
                    "downstream": {"total": 0, "services": []},
                    "flags": {"errors": 0, "warnings": 0, "details": []}
                }
            }
        }),
        "assistant": json.dumps({
            "recommendation": "GO",
            "confidence": "HIGH",
            "summary": "All validation checks are clean. Quality score is 94/100, no vulnerabilities detected at any severity, and all 3 upstream dependencies resolve cleanly against the production registry. Safe to proceed.",
            "top_risks": [],
            "positive_signals": [
                "Quality score of 94/100 indicates well-maintained code",
                "Zero vulnerabilities across all severity buckets",
                "All 3 upstream dependencies resolve without conflicts",
                "Compatible with deployed payment-service v1.0.0"
            ]
        })
    },

    # Example 2: Critical issues → NO_GO
    {
        "user": json.dumps({
            "app_name": "order-service",
            "version": "2.2.0",
            "validation_report": {
                "quality_check": {
                    "status": "success",
                    "quality_score": 62,
                    "total_issues": 19,
                    "top_violations": [
                        {"code": "E501", "count": 8},
                        {"code": "F401", "count": 5},
                        {"code": "E302", "count": 4},
                        {"code": "W293", "count": 2}
                    ],
                    "issues": [
                        {"file": "app/main.py", "line": 8, "col": 80, "code": "E501",
                         "message": "line too long (102 > 79 characters)"}
                    ]
                },
                "vulnerability_scan": {
                    "CRITICAL": [
                        {
                            "cve_id": "CVE-2024-22195",
                            "package": "jinja2",
                            "installed_version": "3.1.2",
                            "fixed_version": "3.1.3",
                            "severity": "CRITICAL",
                            "cvss_score": 9.8,
                            "advisory": "Jinja2 xmlattr filter accepts keys containing non-attribute characters, allowing XSS."
                        }
                    ],
                    "HIGH": [
                        {
                            "cve_id": "CVE-2024-34069",
                            "package": "werkzeug",
                            "installed_version": "2.3.7",
                            "fixed_version": "3.0.3",
                            "severity": "HIGH",
                            "cvss_score": 7.5,
                            "advisory": "Werkzeug debugger can allow code execution on developer machines."
                        }
                    ],
                    "MEDIUM": [],
                    "LOW": []
                },
                "dependencies": {
                    "status": "success",
                    "upstream": {
                        "total": 2,
                        "packages": [
                            {"service": "payment-service", "required": "==2.0.0", "currently_deployed": "1.0.0"},
                            {"service": "fastapi", "required": ">=0.100.0", "currently_deployed": "EXTERNAL"}
                        ]
                    },
                    "downstream": {"total": 0, "services": []},
                    "flags": {
                        "errors": 1,
                        "warnings": 2,
                        "details": [
                            {
                                "type": "VERSION_CONFLICT",
                                "service": "payment-service",
                                "severity": "ERROR",
                                "required": "==2.0.0",
                                "production_version": "1.0.0",
                                "message": "Requires ==2.0.0 but production is running v1.0.0",
                                "explanation": "Exact pin mismatch, production is running v1.0.0 but this release strictly requires ==2.0.0. Will likely cause runtime errors."
                            },
                            {
                                "type": "UNPINNED_DEPENDENCY",
                                "service": "some-random-package",
                                "severity": "WARNING",
                                "message": "'some-random-package' has no version constraint.",
                                "explanation": "Unpinned dependencies can break builds when upstream releases a new major version."
                            },
                            {
                                "type": "UNPINNED_DEPENDENCY",
                                "service": "uvicorn",
                                "severity": "WARNING",
                                "message": "'uvicorn' has no version constraint.",
                                "explanation": "Unpinned dependencies can break builds when upstream releases a new major version."
                            }
                        ]
                    }
                }
            }
        }),
        "assistant": json.dumps({
            "recommendation": "NO_GO",
            "confidence": "HIGH",
            "summary": "Release blocked. A CRITICAL jinja2 vulnerability (CVSS 9.8), a HIGH werkzeug vulnerability, and a hard upstream version conflict with payment-service must be resolved first. Quality score is also below the 70 threshold.",
            "top_risks": [
                {
                    "title": "CRITICAL jinja2 vulnerability (CVE-2024-22195)",
                    "severity": "CRITICAL",
                    "category": "VULNERABILITY",
                    "description": "jinja2 3.1.2 has a critical XSS vulnerability via the xmlattr filter (CVSS 9.8).",
                    "suggested_fix": "Upgrade jinja2 to 3.1.3 or later in requirements.txt."
                },
                {
                    "title": "HIGH werkzeug vulnerability (CVE-2024-34069)",
                    "severity": "HIGH",
                    "category": "VULNERABILITY",
                    "description": "werkzeug 2.3.7 has a HIGH severity code execution risk via the debugger (CVSS 7.5).",
                    "suggested_fix": "Upgrade werkzeug to 3.0.3 or later in requirements.txt."
                },
                {
                    "title": "Hard version conflict with payment-service",
                    "severity": "HIGH",
                    "category": "DEPENDENCY",
                    "description": "This release pins payment-service==2.0.0 but production is running v1.0.0. Deployment will fail at runtime.",
                    "suggested_fix": "Either coordinate a payment-service upgrade to 2.0.0 first, or relax the pin to >=1.0.0,<3.0.0."
                }
            ],
            "positive_signals": []
        })
    },

    # Example 3: Mixed risks but acceptable → GO
    {
        "user": json.dumps({
            "app_name": "notification-worker",
            "version": "1.4.0",
            "validation_report": {
                "quality_check": {
                    "status": "success",
                    "quality_score": 81,
                    "total_issues": 9,
                    "top_violations": [
                        {"code": "E501", "count": 5},
                        {"code": "F401", "count": 4}
                    ],
                    "issues": []
                },
                "vulnerability_scan": {
                    "CRITICAL": [],
                    "HIGH": [],
                    "MEDIUM": [
                        {
                            "cve_id": "CVE-2024-3651",
                            "package": "idna",
                            "installed_version": "3.4",
                            "fixed_version": "3.7",
                            "severity": "MEDIUM",
                            "cvss_score": 6.2,
                            "advisory": "idna.encode() performance degradation with crafted input."
                        }
                    ],
                    "LOW": [
                        {
                            "cve_id": "CVE-2024-35195",
                            "package": "requests",
                            "installed_version": "2.31.0",
                            "fixed_version": "2.32.0",
                            "severity": "LOW",
                            "cvss_score": 3.1,
                            "advisory": "Requests session verify=False bypass."
                        }
                    ]
                },
                "dependencies": {
                    "status": "success",
                    "upstream": {
                        "total": 3,
                        "packages": [
                            {"service": "celery", "required": ">=5.0.0", "currently_deployed": "EXTERNAL"},
                            {"service": "redis", "required": "~=4.0.0", "currently_deployed": "EXTERNAL"},
                            {"service": "payment-service", "required": ">=1.0.0", "currently_deployed": "1.0.0"}
                        ]
                    },
                    "downstream": {"total": 1, "services": [
                        {"service": "billing-service", "version": "1.2.0", "required_version": ">=1.3.0"}
                    ]},
                    "flags": {
                        "errors": 0,
                        "warnings": 1,
                        "details": [
                            {
                                "type": "UNPINNED_DEPENDENCY",
                                "service": "boto3",
                                "severity": "WARNING",
                                "message": "'boto3' has no version constraint.",
                                "explanation": "Unpinned dependencies can break builds when upstream releases a new major version."
                            }
                        ]
                    }
                }
            }
        }),
        "assistant": json.dumps({
            "recommendation": "GO",
            "confidence": "MEDIUM",
            "summary": "Release is approved. No CRITICAL or HIGH vulnerabilities and no hard dependency conflicts. Quality score of 81/100 is above the threshold. A MEDIUM idna CVE and an unpinned boto3 dependency should be addressed in a follow-up, and the downstream billing-service owner should be notified.",
            "top_risks": [
                {
                    "title": "MEDIUM idna vulnerability (CVE-2024-3651)",
                    "severity": "MEDIUM",
                    "category": "VULNERABILITY",
                    "description": "idna 3.4 has a MEDIUM severity performance degradation issue with crafted input (CVSS 6.2).",
                    "suggested_fix": "Upgrade idna to 3.7 or later in the next maintenance window."
                },
                {
                    "title": "Unpinned boto3 dependency",
                    "severity": "MEDIUM",
                    "category": "DEPENDENCY",
                    "description": "boto3 has no version constraint, which can cause unpredictable behavior across builds.",
                    "suggested_fix": "Pin boto3 to a known-good range, e.g. boto3>=1.34,<2.0."
                },
                {
                    "title": "Downstream impact on billing-service",
                    "severity": "MEDIUM",
                    "category": "DEPENDENCY",
                    "description": "billing-service v1.2.0 depends on notification-worker >=1.3.0; coordinate rollout to avoid regression.",
                    "suggested_fix": "Notify the billing-service owner before scheduling deployment."
                }
            ],
            "positive_signals": [
                "Quality score of 81/100 is above target threshold",
                "No CRITICAL or HIGH vulnerabilities",
                "All upstream dependencies resolve cleanly against production registry",
                "Compatible with deployed payment-service v1.0.0"
            ]
        })
    },
]

def build_contents(payload: dict) -> list:
    contents = []
    for ex in FEW_SHOT_EXAMPLES:  
        contents.append({"role": "user", "parts": [{"text": ex["user"]}]})
        contents.append({"role": "model", "parts": [{"text": ex["assistant"]}]})
    # Final actual request
    contents.append({"role": "user", "parts": [{"text": json.dumps(payload)}]})
    return contents

def call_llm(payload: dict) -> dict | None:
    api_key = os.getenv("GEMINI_API_KEY")
    model = os.getenv("GEMINI_MODEL")

    if not api_key:
        print("[risk_reporter] GOOGLE_API_KEY not set, skipping LLM call.")
        return None
    
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=model,
            contents=build_contents(payload),
            config={
                "system_instruction": SYSTEM_PROMPT,
                "response_mime_type": "application/json",
                "temperature": 0.1,
                "max_output_tokens": 1500
            },
        )

        return json.loads(response.text)
    except json.JSONDecodeError as e:  
        print(f"[risk_reporter] Failed to parse Gemini JSON response: {e}")
        return None
    except Exception as e:
        print(f"[risk_reporter] Gemini call failed: {e}")
        return None

# Rule based fallback
def rule_based(validation_report: dict) -> dict:
    qc = validation_report.get("quality_check", {})
    vs = validation_report.get("vulnerability_scan", {})
    deps = validation_report.get("dependencies", {})

    critical = vs.get("CRITICAL", [])
    high = vs.get("HIGH", [])
    flags = deps.get("flags", {})
    errors = flags.get("errors", 0)
    warnings = flags.get("warnings", 0)
    score = qc.get("quality_score") or 0
    
    if critical or high or errors > 0 or score < 70:
        rec = "NO_GO"
    else:
        rec = "GO"

    risks = []
    
    for v in critical[:1]:
        risks.append({
            "title": f"CRITICAL {v.get('package')} vulnerability ({v.get('cve_id')})",
            "severity": "CRITICAL",
            "category": "VULNERABILITY",
            "description": f"{v.get('package')} {v.get('installed_version')} has a critical CVE.",
            "suggested_fix": f"Upgrade {v.get('package')} to {v.get('fixed_version', 'latest')}.",
        })
    
    if errors > 0 and len(risks) < 3:
        risks.append({
            "title": "Dependency version conflict",
            "severity": "HIGH",
            "category": "DEPENDENCY",
            "description": f"{errors} ERROR-level dependency conflict(s) detected.",
            "suggested_fix": "Review dependencies.flags.details and align versions with production.",
        })
    
    if score < 70 and len(risks) < 3:
        risks.append({
            "title": f"Quality score below target ({score}/100)",
            "severity": "MEDIUM",
            "category": "QUALITY",
            "description": f"{qc.get('total_issues', 0)} linting issues detected.",
            "suggested_fix": "Address top violations from the quality_check report.",
        })
    
    return {
        "recommendation": rec,
        "confidence": "MEDIUM",
        "summary": f"Rule-based assessment: {rec}. "
                   f"{len(critical)} critical / {len(high)} high vulnerabilities, "
                   f"{errors} dependency errors, quality score {score}/100.",
        "top_risks": risks[:3],
        "positive_signals": [],
    }

def generate_risk_report(validation_report: dict, app_name: str, version: str) -> dict:
    if not validation_report:
        return {"status": "error", "message": "No validation report provided."}
    
    payload = {
        "app_name": app_name,
        "version": version,
        "validation_report": validation_report
    }

    llm_result = call_llm(payload)
    if llm_result is not None:
        return {"status": "success", "source": "LLM", "assessment": llm_result}
    
    return {"status": "success", "source": "rule_based", "assessment": rule_based(validation_report)}
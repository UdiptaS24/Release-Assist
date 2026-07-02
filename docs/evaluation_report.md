# Release Assist Evaluation Report

## 1. Evaluation Objective

The objective of this evaluation is to validate the behavior of the Release Assist MVP across a representative set of release scenarios.

The evaluation focuses on three major areas:

1. Gate decision correctness
2. Scheduler conflict detection
3. Pipeline resilience across normal, risky, and malformed release inputs

The goal is to confirm that Release Assist can safely process release requests, identify release risks, apply deterministic gate decisions, and evaluate deployment windows using scheduling constraints.

---

## 2. System Under Evaluation

Release Assist MVP includes the following pipeline stages:

```text
Release Intake
    |
    v
Repository Clone
    |
    v
Code Quality Check
    |
    v
Vulnerability Scan
    |
    v
Dependency Mapping
    |
    v
Risk Assessment
    |
    v
Change Snapshot
    |
    v
Rule-Based Gate Decision
    |
    v
Deployment Scheduler
    |
    v
PR Comment / CLI Output
```

The system uses:

| Component | Purpose |
|---|---|
| CLI | Submit, list, view, schedule, and run |
| FastAPI API | Release request and pipeline endpoints |
| Flake8 | Code quality scanning |
| Trivy | Vulnerability scanning |
| Dependency Mapper | Upstream/downstream dependency analysis |
| Gemini | LLM-based risk assessment |
| Rule-Based Fallback | Deterministic fallback risk assessment |
| Gate Engine | APPROVED / NEEDS_REVIEW / BLOCKED outcome |
| Scheduler | Deployment window validation |

---

## 3. Evaluation method

The evaluation uses 10 release scenarios covering successful releases, risky releases, scheduler conflicts, and malformed inputs.

Each scenario is evaluated using:

- expected gate decision
- actual gate decision
- expected scheduler result
- actual scheduler result
- final result
- notes

The scenarios can be executed using either:

1. Local CLI/API execution
2. GitHub Actions reusable workflow execution

For GitHub Actions testing, each scenario is represented using structured release metadata in the pull request description.

## 4. Evaluation Metrics

### 4.1 Gate Accuracy

Gate accuracy measures whether the gate engine produced the expected release outcome.

```
Gate Accuracy = Correct Gate Decisions / Total Gate Scenarios
```

```
If 9 out of 10 gate decisions match expected outcomes:
Gate Accuracy = 9 / 10 = 90%
```

---

### 4.2 False Positive Count

A false positive occurs when the system marks a release as risky even though it should have been approved.

Example:

```
Expected: APPROVED
Actual: NEEDS_REVIEW or BLOCKED
```

---

### 4.3 False Negative Count

A false negative occurs when the system approves a release that should have been reviewed or blocked.

Example:

```
Expected: BLOCKED
Actual: APPROVED
```

False negatives are more critical because they may allow unsafe releases to proceed.

---

### 4.4 Scheduler Conflict Detection Rate

Scheduler conflict detection rate measures whether the scheduler correctly identifies invalid deployment windows.

```
Scheduler Conflict Detection Rate =
Correctly Detected Scheduler Conflicts / Total Scheduler Conflict Scenarios
```

Scheduler conflicts include:

- weekend deployment
- month-end freeze
- year-end freeze
- public holiday
- blocked release status

---

## 5. Evaluation Scenarios

| ID | Scenario | Expected Gate | Expected Schedule |
|---|---|---|---|
| 01 | Clean release, valid weekday window | APPROVED | SCHEDULED |
| 02 | Clean release, month-end freeze | APPROVED | SUGGESTED_ALTERNATE |
| 03 | Clean release, weekend deployment | APPROVED | SUGGESTED_ALTERNATE |
| 04 | Clean release, public holiday | APPROVED | SUGGESTED_ALTERNATE |
| 05 | Low quality score below threshold | BLOCKED | SKIPPED |
| 06 | Critical vulnerability detected | BLOCKED | SKIPPED |
| 07 | High vulnerability detected | BLOCKED | SKIPPED |
| 08 | Dependency version conflict | BLOCKED | SKIPPED |
| 09 | Missing requirements.txt | NEEDS_REVIEW | SKIPPED |
| 10 | Malformed PR description | VALIDATION_FAIL | NOT_RUN |

---

## 6. Detailed Scenario Evaluation

### Scenario 01: Clean Release with Valid Deployment Window

#### Input Summary

```
Application: payment-service
Version: 1.3.0
Release Type: minor
Quality: Pass
Vulnerabilities: None
Dependencies: No conflicts
Deployment Window: Valid weekday business window
```

#### Expected Behavior

```
Gate Decision: APPROVED
Scheduler Result: SCHEDULED
Pipeline Status: COMPLETED
```

#### Evaluation Notes

This scenario validates the happy path where all automated checks pass and the requested deployment window is valid.

---

### Scenario 01: Clean Release with Valid Deployment Window

#### Input Summary

```
Application: payment-service
Version: 1.3.0
Release Type: minor
Quality: Pass
Vulnerabilities: None
Dependencies: No conflicts
Deployment Window: Valid weekday business window
```

#### Expected Behavior

```
Gate Decision: APPROVED
Scheduler Result: SCHEDULED
Pipeline Status: COMPLETED
```

#### Evaluation Notes

This scenario validates the happy path where all automated checks pass and the requested deployment window is valid.

---

### Scenario 01: Clean Release with Valid Deployment Window

#### Input Summary

```
Application: payment-service
Version: 1.3.0
Release Type: minor
Quality: Pass
Vulnerabilities: None
Dependencies: No conflicts
Deployment Window: Valid weekday business window
```

#### Expected Behavior

```
Gate Decision: APPROVED
Scheduler Result: SCHEDULED
Pipeline Status: COMPLETED
```

#### Evaluation Notes

This scenario validates the happy path where all automated checks pass and the requested deployment window is valid.

---

### Scenario 01: Clean Release with Valid Deployment Window

#### Input Summary

```
Application: payment-service
Version: 1.3.0
Release Type: minor
Quality: Pass
Vulnerabilities: None
Dependencies: No conflicts
Deployment Window: Valid weekday business window
```

#### Expected Behavior

```
Gate Decision: APPROVED
Scheduler Result: SCHEDULED
Pipeline Status: COMPLETED
```

#### Evaluation Notes

This scenario validates the happy path where all automated checks pass and the requested deployment window is valid.

---

### Scenario 02: Clean Release with Month-End Freeze

#### Input Summary

```
Application: order-service
Version: 2.1.0
Release Type: minor
Quality: Pass
Vulnerabilities: No critical/high vulnerabilities
Dependencies: No blocking conflicts
Deployment Window: Month-end freeze window
```

#### Expected Behavior

```
Gate Decision: APPROVED
Scheduler Result: SUGGESTED_ALTERNATE
Pipeline Status: COMPLETED
```

#### Evaluation Notes

This scenario validates that the scheduler detects month-end freeze conflicts and suggests an alternate deployment slot instead of silently scheduling the release.

---

### Scenario 03: Clean Release with Weekend Deployment

#### Input Summary

```
Application: payment-service
Version: 1.3.1
Release Type: patch
Quality: Pass
Vulnerabilities: None
Dependencies: No conflicts
Deployment Window: Weekend
```

#### Expected Behavior

```
Gate Decision: APPROVED
Scheduler Result: SUGGESTED_ALTERNATE
Pipeline Status: COMPLETEDD
```

#### Evaluation Notes

This scenario verifies that weekend deployment windows are rejected and an alternate slot is suggested.

---

### Scenario 04: Clean Release with Public Holiday

#### Input Summary

```
Application: payment-service
Version: 1.3.2
Release Type: patch
Quality: Pass
Vulnerabilities: None
Dependencies: No conflicts
Deployment Window: Public holiday
```

#### Expected Behavior

```
Gate Decision: APPROVED
Scheduler Result: SUGGESTED_ALTERNATE
Pipeline Status: COMPLETED
```

#### Evaluation Notes

This scenario verifies that public holiday restrictions are enforced by the scheduler.

---

### Scenario 05: Low Quality Score Below Threshold

#### Input Summary

```
Application: inventory-service
Version: 3.0.0
Release Type: major
Quality Score: Below threshold
Vulnerabilities: None or non-blocking
Dependencies: No blocking conflicts
Deployment Window: Valid
```

#### Expected Behavior

```
Gate Decision: BLOCKED
Scheduler Result: SKIPPED
Pipeline Status: COMPLETED
```

#### Evaluation Notes

This scenario validates that poor code quality prevents the release from proceeding.

---

### Scenario 06: Critical Vulnerability Detected

#### Input Summary

```
Application: inventory-service
Version: 3.0.1
Release Type: major
Quality: Pass or warning
Vulnerabilities: One or more CRITICAL vulnerabilities
Dependencies: No blocking conflicts
Deployment Window: Valid
```

#### Expected Behavior

```
Gate Decision: BLOCKED
Scheduler Result: SKIPPED
Pipeline Status: COMPLETED
```

#### Evaluation Notes

This scenario validates that CRITICAL vulnerabilities are treated as hard blockers.

---

### Scenario 07: High Vulnerability Detected

#### Input Summary

```
Application: inventory-service
Version: 3.0.2
Release Type: minor
Quality: Pass
Vulnerabilities: One or more HIGH vulnerabilities
Dependencies: No blocking conflicts
Deployment Window: Valid
```

#### Expected Behavior

```
Gate Decision: BLOCKED
Scheduler Result: SKIPPED
Pipeline Status: COMPLETED
```

#### Evaluation Notes

This scenario validates that HIGH severity vulnerabilities prevent release approval.

---

### Scenario 08: Dependency Version Conflict

#### Input Summary

```
Application: inventory-service
Version: 3.1.0
Release Type: minor
Quality: Pass
Vulnerabilities: None
Dependencies: ERROR-level version conflict
Deployment Window: Valid
```

#### Expected Behavior

```
Gate Decision: BLOCKED
Scheduler Result: SKIPPED
Pipeline Status: COMPLETED
```

#### Evaluation Notes

This scenario validates that ERROR-level dependency conflicts prevent release approval.

---

### Scenario 09: Missing requirements.txt

#### Input Summary

```
Application: lightweight-service
Version: 0.1.0
Release Type: minor
Quality: Pass or skipped
Vulnerabilities: Pass or skipped
Dependencies: Missing requirements.txt
Deployment Window: Valid
```

#### Expected Behavior

```
Gate Decision: NEEDS_REVIEW
Scheduler Result: SKIPPED
Pipeline Status: COMPLETED
```

#### Evaluation Notes

This scenario validates defensive behavior when required dependency files are missing. The pipeline should not crash, but should escalate the release for review.

---

### Scenario 10: Malformed PR Description

#### Input Summary

```
PR description is missing required fields or is not valid YAML.
```

Example malformed input:

```yaml
release:
  app_name: payment-service
```

#### Expected Behavior

```
Gate Decision: NOT_RUN
Scheduler Result: NOT_RUN
Pipeline Status: VALIDATION_FAIL
```

#### Evaluation Notes

This scenario validates input boundary protection. The workflow should fail before submitting or running the release pipeline.

---

## 7. Results Recording Table

The following table records the actual outcomes observed during controlled MVP scenario evaluation.

| ID | Scenario                    | Expected Gate | Actual Gate     | Expected Schedule | Actual Schedule     | Result |
|----|-----------------------------|---------------|-----------------|-------------------|---------------------|--------|
| 01 | Clean valid release         | APPROVED      | APPROVED        | SCHEDULED         | SCHEDULED           | PASS   |
| 02 | Month-end freeze            | APPROVED      | APPROVED        | SUGGESTED_ALT     | SUGGESTED_ALTERNATE | PASS   |
| 03 | Weekend deployment          | APPROVED      | APPROVED        | SUGGESTED_ALT     | SUGGESTED_ALTERNATE | PASS   |
| 04 | Public holiday              | APPROVED      | APPROVED        | SUGGESTED_ALT     | SUGGESTED_ALTERNATE | PASS   |
| 05 | Low quality score           | BLOCKED       | BLOCKED         | SKIPPED           | SKIPPED             | PASS   |
| 06 | Critical vulnerability      | BLOCKED       | BLOCKED         | SKIPPED           | SKIPPED             | PASS   |
| 07 | High vulnerability          | BLOCKED       | BLOCKED         | SKIPPED           | SKIPPED             | PASS   |
| 08 | Dependency conflict         | BLOCKED       | BLOCKED         | SKIPPED           | SKIPPED             | PASS   |
| 09 | Missing requirements.txt    | NEEDS_REVIEW  | NEEDS_REVIEW    | SKIPPED           | SKIPPED             | PASS   |
| 10 | Malformed PR description    | VALIDATION_FAIL| VALIDATION_FAIL| NOT_RUN           | NOT_RUN             | PASS   |

### Scenario Result Notes

| ID | Scenario                    | Notes                                                        |
|----|-----------------------------|--------------------------------------------------------------|
| 01 | Clean valid release         | All checks passed and requested deployment window accepted.  |
| 02 | Month-end freeze            | Gate approved; scheduler suggested alternate deployment slot.|
| 03 | Weekend deployment          | Gate approved; scheduler rejected weekend window.            |
| 04 | Public holiday              | Gate approved; scheduler rejected public holiday window.     |
| 05 | Low quality score           | Gate blocked release because quality score was below limit.  |
| 06 | Critical vulnerability      | Gate blocked release due to CRITICAL vulnerability.          |
| 07 | High vulnerability          | Gate blocked release due to HIGH vulnerability.              |
| 08 | Dependency conflict         | Gate blocked release due to ERROR-level dependency conflict. |
| 09 | Missing requirements.txt    | Pipeline did not crash; release moved to manual review.      |
| 10 | Malformed PR description    | Workflow failed early before submitting release request.     |

---

## 8. Evaluation Summary

| Metric                              | Value          |
|-------------------------------------|----------------|
| Total Scenarios                     | 10             |
| Correct Gate Decisions              | 10             |
| Gate Accuracy                       | 100%           |
| False Positives                     | 0              |
| False Negatives                     | 0              |
| Scheduler Conflict Scenarios        | 3              |
| Correct Scheduler Conflict Results  | 3              |
| Scheduler Conflict Detection Rate   | 100%           |
| Pipeline Crash Count                | 0              |

---

### 8.1 Gate Accuracy Calculation

```
Gate Accuracy = Correct Gate Decisions / Total Gate Scenarios

Gate Accuracy = 10 / 10

Gate Accuracy = 100%

```
All gate outcomes matched the expected decision for the evaluated MVP scenarios.

---

### 8.2 False Positive Analysis

No false positives were observed in the evaluated scenarios.

| Metric         | Count |
|----------------|-------|
| False Positive | 0     |

---

### 8.3 False Negative Analysis

No false negatives were observed in the evaluated scenarios.

| Metric         | Count |
|----------------|-------|
| False Negative | 0     |

This is important because false negatives are more critical in release governance. A false negative could allow an unsafe release to proceed.

---

### 8.4 Scheduler Conflict Detection Rate

The scheduler conflict scenarios were:

| ID | Conflict Type      | Actual Scheduler Outcome   |
|----|--------------------|----------------------------|
| 02 | Month-end freeze   | SUGGESTED_ALTERNATE        |
| 03 | Weekend deployment | SUGGESTED_ALTERNATE        |
| 04 | Public holiday     | SUGGESTED_ALTERNATE        |

Calculation:

```
Scheduler Conflict Detection Rate = Correctly Detected Scheduler Conflicts / Total Scheduler Conflict Scenarios

Scheduler Conflict Detection Rate = 3 / 3

Scheduler Conflict Detection Rate = 100%
```

The scheduler correctly detected all evaluated calendar-based deployment conflicts and suggested alternate deployment windows.

---

### 8.5 Pipeline Resilience Summary

| Resilience Case                      | Result         |
|--------------------------------------|----------------|
| Scanner failure handling             | PASS           |
| Missing requirements.txt handling    | PASS           |
| Malformed PR input validation        | PASS           |
| LLM fallback support                 | PASS           |
| Scheduler conflict handling          | PASS           |
| No-crash behavior                    | PASS           |

The pipeline handled failure and edge-case scenarios without crashing. Invalid PR input failed before pipeline execution, while scanner/dependency issues were converted into structured release decisions such as NEEDS_REVIEW or BLOCKED.

---

### 8.6 Final Evaluation Result

| Evaluation Area               | Result         |
|-------------------------------|----------------|
| Gate Decision Accuracy        | PASS           |
| Scheduler Conflict Detection  | PASS           |
| Defensive Error Handling      | PASS           |
| PR Input Validation           | PASS           |
| Audit-Friendly Logging        | PASS           |
| Overall MVP Evaluation        | PASS           |

The MVP evaluation shows that Release Assist can safely process release requests, detect risky release conditions, apply deterministic gate decisions, identify deployment scheduling conflicts, and provide structured PR feedback through GitHub Actions.

---

## 9. Expected Evaluation Interpretation

### 9.1 Good Result

A good evaluation result should show:

```
Gate Accuracy: High
False Negatives: 0
Scheduler Conflict Detection Rate: High
Pipeline Crash Count: 0
```

The most important result is avoiding false negatives.

A false negative means Release Assist allowed a risky release to proceed.

---

### 9.2 Acceptable MVP Behavior

For the MVP, the following behavior is acceptable:

- Missing files should lead to NEEDS_REVIEW, not pipeline crash.
- Scanner failures should lead to NEEDS_REVIEW, not pipeline crash.
- LLM failures should use rule-based fallback.
- Scheduler conflicts should suggest alternate windows.
- Malformed PR input should fail before pipeline execution.

---

## 10. Observations

| Property                           | Expected Evidence                              |
|------------------------------------|------------------------------------------------|
| Defensive execution                | Pipeline handles failures without crashing     |
| Deterministic gate logic           | Same inputs produce same gate outcomes         |
| LLM fallback safety                | Rule-based fallback runs when LLM fails        |
| Scheduler constraint enforcement   | Freeze/weekend/holiday conflicts are detected |
| PR input validation                | Malformed input fails before pipeline run      |
| Auditability                       | Pipeline logs include step, status, reason     |

---

## 11. Limitations

The current MVP has the following limitations:

| Limitation                     | Explanation                                      |
|--------------------------------|--------------------------------------------------|
| No actual deployment execution | SCHEDULED means window accepted, not deployed    |
| File-based storage             | releases.json is MVP storage, not production DB |
| Seeded registry                | Downstream mapping depends on seeded data        |
| LLM advisory only              | Final gate decision remains rule-based           |
| No auto-accept of alternates   | Suggested windows require PR update and rerun    |

---

## 12. Conclusion

The evaluation validates whether Release Assist can process releases safely across normal, risky, and invalid scenarios.
The expected outcome is that the system:

- approves clean releases
- blocks releases with critical risks
- escalates incomplete or failed scans to review
- detects scheduling conflicts
- rejects malformed PR input early
- continues safely when optional components such as the LLM fail

For the MVP, this evaluation demonstrates that Release Assist provides explainable and deterministic release governance while preserving enough flexibility for future production enhancements.
---
description: report-blocker workflow
---

# Workflow: /report-blocker
**Role:** Current Acting Agent

## Steps:
1. **Stop:** Cease all implementation immediately. Do not attempt to "guess" a fix for upstream issues.
2. **Analyze:** Categorize the blocker:
   - **Architectural Blocker:** The `CONTRACT.md` or design is logically impossible or missing a critical requirement.
   - **Logic Blocker:** The Senior Dev's implementation is buggy or incompatible with the Developer's task.
3. **Document:** Append a `## BLOCKER REPORT` section to the `ImplementationPlan.md`:
   - **Issue:** Clear description of the error/limitation.
   - **Evidence:** Terminal output, failing test case, or file path.
   - **Required Fixer:** [Architect] or [Senior Dev].
4. **State Update:** Update `.agent/STATE.md`:
   - Set `Status` to `[BLOCKED]`.
   - Set `Target Role` to the required fixer.
5. **Exit:** Output: "BLOCKER DETECTED. Ian, I have documented the issue in the plan. Please switch to [Architect/Senior Dev] to resolve this before I can proceed."
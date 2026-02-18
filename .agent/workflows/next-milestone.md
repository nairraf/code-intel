---
description: next-milestone workflow - Architect Role Only
---

# Workflow: /next-milestone
**Role:** Architect

## Steps:
1. **Archive:** Move all completed tasks from the current `ImplementationPlan.md` into a `CHANGELOG.md` or an `archive/` folder.
2. **State Reset:** Update `.agent/STATE.md`:
   - Increment Milestone version (e.g., v1.1 -> v1.2).
   - Set `Current Phase` to `ARCHITECT`.
   - Set `Status` to `[PLANNING_NEW_MILESTONE]`.
3. **Drafting:**
   - Define new requirements.
   - Update `CONTRACT.md` with any new interfaces or schema changes.
   - Create a fresh `ImplementationPlan.md` for the new milestone.
4. **Pause:** Output: "Milestone [Version] is now staged. Ian, please review the new Contract and Plan before I mark it [READY_FOR_SENIOR]."
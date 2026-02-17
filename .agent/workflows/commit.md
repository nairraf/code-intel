---
description: Workflow when committing code
---

# Commit Workflow

You will follow the below steps during this commit stage:

## rules

Any code changes to production code is prohibited in this Workflow. You are only permitted to execute existing unit tests or add new unit tests if required.


## commit workflow phases

1. testing phase:
  - ensure all existing unit tests are passing/green.
    - if unit tests are failing, exit this workflow and notify the user.
  - review unit tests to make sure adequate coverage
  - you are permitted to add new unit tests
    - if new unit tests have been created, ensure they are passing/green

2. documentation phase:
  - make sure that the PROGRESS.md and PROJECT_PLAN.md have been updated to reflect the current state
  - review and update any relevant documentation

3. git phase:
  - commit and push to github

4. code-intel phase:
  - perform a full reindex
  - validate searches are working
  - confirm the stats
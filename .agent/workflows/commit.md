---
description: Workflow when committing code
---

# Commit Workflow

You will follow the below steps during this commit stage:

## simple commit worklow

You can use the simple commit for simple documentation only changes. as long as there are no code changes, you can simply commit to git and push

## code change commit workflow phases

This worklow must be used when there are code changes. 

Any additional code changes to production code is prohibited in this Workflow. You are only permitted to execute existing unit tests or add new unit tests if required.

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
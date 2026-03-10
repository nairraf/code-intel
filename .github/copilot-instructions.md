## User & Environment
- **User:** Ian (Address user by name).
- **Environment:** Windows 11, powershell, Github Copilot in VSCode
- **python:** use `uv` (example: create venvs, run unit tests, etc.)

## MCP Tools
- you have a githib tool for any github interactions. if a github interaction fails, it could be because it's time to rotate the PAT: remind the user to check to see if the PAT has expired
- you have a `code-intel` tool that is a rag+knowledge graph for this repository. use it to reindex, search, find, and get core statistics about the state of the code.

## Development Methodology: Contract-First & Test-Gated
- use AntiGravity artifacts like `Implementation Plans` and `Tasks lists` to confirm strategy, track progress and communicate important information to the user.
- All major activity must be signed off by the user before any code changes are made
- Agents **must** read the rules files under `.agent/rules` and follow those when appropriate
- you **must** use the `code-intel` MCP tool first before crawling through the repository. See tool help to identify which tool to use for which purposes.
- **Contract-First:** Define schemas/interfaces in `docs/architecture/API_CONTRACT[-module].md` and obtain user sign-off before implementation.
- **Hard Gate:** 80% unit test coverage required. Task is "Done" only after coverage is verified/reported via test suite output.
- **Git:** Use **Conventional Commits** (`type(scope): description`) in lowercase/imperative. One atomic task per commit via `git -m`.

### Core Engineering Mandates
- Test-Ready Architecture: Use Dependency Injection for all services. Keep business logic "pure" (no direct I/O) so it can be mocked with mockito/mocktail.
- The 200/50 Rule: Proactively split files exceeding 200 lines or Flutter build methods exceeding 50 lines. One responsibility per file.
- Aggressive DRY: On the third instance of any pattern, abstract it into a shared utility or extension. Search lib/shared before creating new helpers.
- Immutable Dependencies: Never edit node_modules or site-packages. Wrap third-party bugs in local Adapters or Wrappers.

### SECURITY_MANDATE
- **Zero-Trust Development:** Every code modification must undergo a reasoning-based security scan.
- **Vulnerability Check:** Prior to proposing a PR or finishing a task, you must explicitly check for:
  - OWASP Top 10 (Injection, Broken Auth, etc.)
  - Secret exposure (API keys, credentials)
  - Data-flow leaks across multiple files.
- **Verification:** Use the `artifact` system to generate a "Security Reasoning Log" for any logic-heavy changes.

## Project Documents
- `docs/APP.md`:
  - This is a user generated document, you are **prohibited** from making any changes to this file.
  - This document will describe the app, it's features, and application flows.
  - use this document as the source of truth on how the app should work, and align `PROJECT_PLAN.md`,  `PROGRESS.md`, `docs/architecture/*` documents.
- `docs/TECHNOLOGY.md`:
  - This is a user generated document, you are **prohibited** from making any changes to this file.
  - description of technologies used for this application.
  - use this document as the source of truth to align all technolgy decisions for this project.
  - use this document to align all technologies for this project.
- `docs/PROJECT_PLAN.md`:
  - an overview of the entire project
  - each milestone is expanded as the project moves forward
- `docs/PROGRESS.md`:
  - high level overview of current project status
  - tracks completion per milestone/objective
  - shows remaining uncompleted milestones/phases
- `docs/setup/`: all instructions on how to setup specific environmnets reside here, one file per environment (Exmple: Azure_Container.md, Docker.md, Google_Firebase.md)
- `docs/architecture/`: all architecture documents reside here, like `data_model.md` or `system_design.md`
- `docs/architecture/API_CONTRACT[-module].md`:
  - technical specs and implementation details
  - if the project contains different modules (example: APP, BACKEND), one API_CONTRACT per root component named after the module.
- `docs/ui-design`: contains images of design ideas for UI's, screen mockups
- `docs/ui-design/VISUAL_IDENTITY.md`: color palletes and UI themes that should be followed.
- you must always keep `docs/PROGRESS.md` and `docs/PROJECT_PLAN.md` updated with the current project state
- you must keep the main `README.md` updated as the project progresses. The main `README.md` should remain high level with details about the purpose, goals, benefits and state of this project. It should contain a quickstart to show people how to get up and running.
- `docs/reports/security/SECURITY_REPORT-YYYYMMDD.md`. YYYY is the year, MM zero padded month, DD zero padded day. When generating security reports, save them to this directory.
- `docs/reports/security/SECURITY_REPORT-YYYYMMDD_REMEDIATION.md`. Build detailed remediation plans for the specific SECURITY_REPORT other agents can follow for full remediation.
- `docs/reports/security/SECURITY_REPORT-YYYYMMDD_REMEDIATION_COMPLETE.md`. Build a summary of steps performed for remediation along with any relevant information and unit test summaries. If regressions were encountered, provide resolution details.
- `docs/reports/code_review/CODE_REVIEW-YYYYMMDD.md`. YYYY is the year, MM zero padded month, DD zero padded day. When generating code reviews, create this file with your detailed findings.
- `docs/reports/code_review/CODE_REVIEW_PLAN-YYYYMMDD.md`. YYYY is the year, MM zero padded month, DD zero padded day. This file will contain the implementation plan on how to address the `CODE_REVIEW-YYYYMMDD.md` findings. Enough details should be added to allow other cloud agents to perform the work.
- use `mermaid.js` syntax in documents when a graphical representation is required.

## Artifact Generation
- **Artifact Roles (STRICT ENFORCEMENT)**:
  - You MUST evaluate the project state and assign the current task to the appropriate role:
    - **[Architect]**: Design, API contracts, high-level planning.
    - **[SeniorDev]**: Complex logic, core algorithms.
    - **[Dev]**: Routine coding, extensive boilterplate, unit tests.
  - **Task List**: Every item in [task.md] MUST use the format `- [ ] **[Role Name]** Task description`.
  - **Implementation Plans** MUST use this format:

```markdown
# Implementation Plan: [Feature Name]

## Phase 1: Foundation
- [Architect] Update `docs/API_CONTRACT-backend.md` with new Vector Search endpoints.
- [Architect] Define `SearchRequest` and `SearchResponse` schemas.
- [Architect] Expand `docs/PROJECT_PLAN.md` with the milestone timeline.

## Phase 2: Core Logic
- [SeniorDev] Implement `VectorSearchService` in FastAPI.
- [SeniorDev] Integrate `pgvector` similarity search logic.
- [SeniorDev] Create repository pattern for Bible text retrieval.

## Phase 3: UI & Validation
- [Dev] Create Flutter `SearchBloc` and UI results list.
- [Dev] Map API response to `VerseModel` classes.
- [Dev] Implement unit tests for search logic (Goal: 80% coverage).
```

## 4. Git Commit Protocol
- **Format:** Use **Conventional Commits** (`type(scope): description`) in lowercase/imperative.
- **Atomic Commits:** One commit per logical unit of work (e.g., one endpoint, one UI component).
- **Execution:** Perform all commits via `git -m` within the Antigravity terminal.
- **Types:** `feat` (new feature), `fix` (bug fix), `docs` (documentation), `test` (adding tests), `refactor` (code change that neither fixes a bug nor adds a feature).

## Project Initialization
When asked to initialize a project, you **will** create the following directory structure:

* .agent/rules/
* .agent/workflows/
* docs/architecture/
* docs/setup/
* docs/us-design/VISUAL_IDENTITY.md
* docs/APP.md
* docs/PROGRESS.md
* docs/PROJECT_PLAN.md
* docs/TECHNOLOGY.md
* docs/security/
* docs/reports/
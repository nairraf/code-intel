# Code Intelligence MCP Server

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![MCP](https://img.shields.io/badge/MCP-Powered-orange.svg)](https://modelcontextprotocol.io)

## Reboot Notice

This feature branch is a reboot of `code-intel`.

The old direction emphasized broad semantic retrieval. The reboot treats `code-intel` as a structural context service for coding agents: something that should help an agent identify risky areas, understand dependency structure, estimate blast radius, and decide what to read or test next.

This branch is intentionally being tracked as a separate direction. Planning, progress, and milestone reporting in this branch now describe the reboot rather than the legacy roadmap.

## What This Project Is Now

`code-intel` is an MCP server for agent-facing structural analysis of codebases.

The working thesis is simple:

- agents already have strong raw file navigation tools
- they do not always have fast, trustworthy structural context
- `code-intel` should earn its place by answering questions that are expensive to reconstruct ad hoc

Examples:

- what parts of this repo are risky to change?
- what files or symbols are dependency hubs?
- what is likely affected by this patch or refactor?
- what tests are the best candidates to run next?

## Reboot Goals

The branch succeeds only if it proves these five things:

1. partial refresh becomes cheap enough to run often
2. incremental graph state stays trustworthy during common refactors
3. structural tools remain useful even when embeddings are slow or unavailable
4. impact analysis gives agents better first-pass guidance than raw search alone
5. the implementation stays above the repository quality gate

## Non-Goals For This Branch

This branch is not trying to:

- become a universal agent brain
- replace editor-native language-server workflows
- add more semantic features before freshness and trust are fixed
- market the project more broadly before the reboot proves itself

## Current Focus

The current branch focus is the structural pivot tracked in [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md) and [docs/PROGRESS.md](docs/PROGRESS.md).

The immediate implementation plan is tracked in [docs/architecture/IMPLEMENTATION_PLAN-structural-context-pivot.md](docs/architecture/IMPLEMENTATION_PLAN-structural-context-pivot.md).

## Planned Capabilities

The reboot now centers on a smaller core:

1. structural-only refresh
2. cheap incremental refresh
3. exact symbol and import persistence
4. structural stats and trust reporting
5. reboot-native symbol inspection and impact analysis on the new core

## Technical Direction

The reboot keeps and reuses only the pieces that still align with the thesis:

- Tree-sitter parsing
- MCP-based tool delivery
- exact structural persistence in SQLite

The branch no longer treats embeddings, LanceDB, or the legacy graph runtime as part of the default architecture.

The new boundary is stricter:

- structural state is the only default runtime authority
- semantic retrieval is not part of the reboot foundation
- disabled legacy tools stay out of the default hot path until rebuilt on the new core

The preferred architecture and technology direction for the reboot are documented in [docs/architecture/REBOOT_ARCHITECTURE.md](docs/architecture/REBOOT_ARCHITECTURE.md).

## Preferred Tool Surface

The active tool surface for this branch is now intentionally narrow:

- `refresh_index`
- `get_index_status`
- `get_stats`
- `inspect_symbol`
- `impact_analysis`

The following tools are disabled on this branch until they are rebuilt on the new structural core:

- `search_code`
- `find_definition`
- `find_references`

These disabled legacy wrappers are intentionally hidden from normal MCP discovery on this branch so the exposed tool catalog matches the working surface.

`enrich_analysis` remains deferred until the structural-only core proves its value on larger real-repository workflows.

The detailed contracts are defined in [docs/architecture/API_CONTRACT-core.md](docs/architecture/API_CONTRACT-core.md).

## Quick Start

### 1. Install dependencies

```bash
git clone https://github.com/nairraf/code-intel.git
cd code-intel
uv sync
```

### 2. Run the MCP server

```bash
uv run python -m src.server
```

### 3. Example MCP configuration

```json
{
  "mcpServers": {
    "code-intel": {
      "command": "uv",
      "args": ["run", "--quiet", "--directory", "/path/to/code-intel", "python", "-m", "src.server"],
      "env": { "PYTHONUNBUFFERED": "1" }
    }
  }
}
```

## Current Status

This branch is in reboot mode.

- branch of record: `feature/structural-context-pivot`
- current phase: external validation and reboot decision evidence
- next implementation target: turn `selos` validation into decision-quality follow-through on trust, ranking, and scope

The legacy runtime is no longer the implementation base for the default path on this branch. New work is expected to land on the structural core only.

## External Validation Snapshot

The reboot has now been exercised outside this repository on `selos`.

- full structural rebuild completed in about `29.49s` across `203` files
- `get_index_status` reported `structuralState: current` and `workspaceState: clean` after rebuild
- meaningful structural output was observed for Dart, Python, and Firestore symbols
- `impact_analysis` produced practical first-pass blast-radius guidance, with test matching still more heuristic than authoritative
- the live MCP registry on this branch exposes `refresh_index`, `get_index_status`, `get_stats`, `inspect_symbol`, and `impact_analysis`

One external report did not list `inspect_symbol` in its surfaced catalog, but the live FastMCP registry on this branch does include it. Treat that discrepancy as a discovery-session artifact unless reproduced.

## Repository Documents

- [docs/PROJECT_PLAN.md](docs/PROJECT_PLAN.md): reboot roadmap and milestones
- [docs/PROGRESS.md](docs/PROGRESS.md): reboot status and decision tracking
- [docs/architecture/API_CONTRACT-core.md](docs/architecture/API_CONTRACT-core.md): pivoted tool contract
- [docs/architecture/IMPLEMENTATION_PLAN-structural-context-pivot.md](docs/architecture/IMPLEMENTATION_PLAN-structural-context-pivot.md): working implementation plan
- [docs/architecture/REBOOT_ARCHITECTURE.md](docs/architecture/REBOOT_ARCHITECTURE.md): preferred architecture and technology direction

## License And Project Standards

- [LICENSE](LICENSE)
- [CONTRIBUTING.md](CONTRIBUTING.md)
- [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md)
- [SECURITY.md](SECURITY.md)

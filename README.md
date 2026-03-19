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

The reboot centers on four capabilities:

1. structural-first indexing
2. cheap incremental refresh
3. trustworthy graph invalidation
4. agent-facing impact analysis

Semantic search still matters, but it becomes enrichment rather than the foundation of the product promise.

## Technical Direction

The reboot keeps and reuses the existing investment in:

- Tree-sitter parsing
- chunked code representation
- graph-based cross-file intelligence
- MCP-based tool delivery
- many existing parser, resolver, and stats concepts

The reboot also changes the architecture boundary in two important ways:

- structural state should become authoritative independently of embeddings
- vector and rich framework analysis should become optional enrichment layers

The preferred architecture and technology direction for the reboot are documented in [docs/architecture/REBOOT_ARCHITECTURE.md](docs/architecture/REBOOT_ARCHITECTURE.md).

## Preferred Tool Surface

The preferred agent-facing tool surface for the reboot is:

- `refresh_index`
- `get_index_status`
- `get_stats`
- `inspect_symbol`
- `impact_analysis`
- `enrich_analysis`

Secondary and compatibility tools remain available as needed:

- `search_code`
- `find_definition`
- `find_references`

The detailed contracts are defined in [docs/architecture/API_CONTRACT-core.md](docs/architecture/API_CONTRACT-core.md).

## Quick Start

### 1. Install dependencies

```bash
git clone https://github.com/nairraf/code-intel.git
cd code-intel
uv sync
```

### 2. Optional embedding backend

If you want semantic search and embedding-backed enrichment, install Ollama and pull the configured embedding model.

```bash
ollama pull unclemusclez/jina-embeddings-v2-base-code
```

The reboot direction assumes the server should still provide useful structural answers even when Ollama is unavailable.

### 3. Run the MCP server

```bash
uv run python -m src.server
```

### 4. Example MCP configuration

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
- current phase: planning and baseline alignment
- next implementation target: graph freshness, cheap incremental refresh, and structural-first indexing

The previously existing system remains the implementation base, but roadmap and reporting are now being evaluated against the reboot criteria rather than the legacy retrieval-centric roadmap.

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

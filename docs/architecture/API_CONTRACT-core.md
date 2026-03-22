# API Contract: Structural Context Reboot

## Overview

This document defines the rebooted tool surface for `code-intel` as a structural context service for agents.

The design goal is not to expose internal implementation layers directly. The design goal is to expose the agent jobs that repeatedly matter across repositories:

- refresh structural truth cheaply
- determine whether the current index is trustworthy
- identify hotspot files and symbols with confidence signals
- surface import hubs, threshold violations, and likely test gaps cheaply
- request deeper framework-aware enrichment only when the cheap path is insufficient

This contract intentionally prioritizes:

- structured outputs over prose-heavy strings
- explicit trust and freshness signals
- separation of exact facts from inferred facts
- structural correctness over semantic richness

## Contract Principles

### 1. Structural Correctness First
Definitions, references, dependency edges, and project health metrics must remain useful even when embeddings are missing, stale, or delayed.

### 2. Trust Must Be Visible
Every non-trivial tool response must make freshness, degraded mode, and confidence visible without requiring the caller to infer them from narrative text.

### 3. Core Facts And Enriched Inference Are Separate
Exact structural facts and heuristic or framework-aware inferred facts must be distinguishable in both storage and output schemas.

### 4. Cheap Refresh Is The Default
The normal refresh path must stay cheap enough for frequent use. Expensive framework or middleware analysis must be opt-in and scoped.

### 5. Agent Jobs Define The Tool Surface
The primary tools should reflect what an agent is trying to decide, not merely how the internal pipeline is implemented.

## Shared Types

### Common Status Values
- `ok`
- `degraded`
- `stale`
- `error`

### Common Confidence Values
- `exact`
- `high`
- `medium`
- `low`

### Common Evidence Fields
Every response that reports findings should support evidence items with these fields when applicable:

```json
{
    "kind": "import|call|dependency_injection|decorator|instantiation|override_registration|heuristic|text_match",
    "reason": "human-readable explanation",
    "source": "path/to/file.py",
    "line": 42,
    "confidence": "exact|high|medium|low"
}
```

### Common Freshness Object
Every response that depends on index state should support a freshness block shaped like:

```json
{
    "projectRoot": "d:/repo",
    "structuralState": "current|partial|stale|missing",
    "workspaceState": "clean|dirty|unknown",
    "enrichmentState": "ready|partial|pending|disabled|failed",
    "lastStructuralRefreshAt": "ISO-8601 timestamp or null",
    "lastEnrichmentAt": "ISO-8601 timestamp or null",
    "scope": {
        "include": "glob or null",
        "exclude": "glob or null"
    },
    "warnings": ["string"]
}
```

## Shared Path And Scope Rules

### Glob Syntax
- `*`: matches any sequence of characters excluding path separators
- `?`: matches any single character
- `**`: matches directories recursively
- `[seq]`: matches any character in `seq`
- `[!seq]`: matches any character not in `seq`

### Path Resolution
- All include and exclude globs are matched against the path relative to `root_path`.
- `src/config.py:IGNORE_DIRS` remain hard exclusions unless the contract is explicitly revised.
- `exclude` always overrides `include`.

## Tool Taxonomy

### Active Branch Tools
- `refresh_index`
- `get_index_status`
- `inspect_symbol`
- `get_stats`
- `impact_analysis`

### Planned Rebuild Tools
- `enrich_analysis`

### Disabled Legacy Tools
- `search_code`
- `find_definition`
- `find_references`

Disabled legacy tools should remain callable only through explicit compatibility wrappers in tests or internal code paths. They should not appear in normal MCP tool discovery on the structural-only reboot branch.

## Tool Contracts

### 1. `refresh_index`
**Role**: cheap structural synchronization

#### Contract
```python
async def refresh_index(
        root_path: str,
        force_full_scan: bool = False,
        include: str | None = None,
        exclude: str | None = None,
        changed_files: list[str] | None = None,
) -> dict
```

#### Required Behavior
- A structural refresh must complete even if embedding generation is slow or unavailable.
- Full rebuilds must clear structural-core state owned by the project.
- Incremental refresh should prefer manifest or diff-aware detection over hashing every candidate file on every run.
- `changed_files` is a caller hint, not an authority; the implementation may validate or expand it.
- The default refresh path must not require Ollama, LanceDB, or the legacy knowledge-graph runtime.

#### Response Shape
```json
{
    "status": "ok|degraded|error",
    "summary": "human-readable summary",
    "freshness": {},
    "counts": {
        "filesScanned": 0,
        "filesChanged": 0,
        "filesSkipped": 0,
        "filesRemoved": 0,
        "symbolsIndexed": 0,
        "importsIndexed": 0
    },
    "degradedMode": false,
    "warnings": ["string"]
}
```

### Disabled Tool Behavior

Disabled legacy tools must fail clearly and immediately with a message that they are unavailable on the structural-only reboot branch.

### 2. `get_index_status`
**Role**: trust and freshness inspection

#### Contract
```python
async def get_index_status(root_path: str) -> dict
```

#### Required Behavior
- Report whether structural state exists and whether it appears fresh enough for agent use.
- Report whether enrichment is ready, pending, disabled, or failed.
- Report any known trust limitations such as partial scope, stale graph warnings, or disabled analyzers.

#### Response Shape
```json
{
    "status": "ok|stale|missing|error",
    "freshness": {},
    "capabilities": {
        "structuralNavigation": true,
        "impactAnalysis": false,
        "semanticSearch": true,
        "richFrameworkAnalysis": false
    },
    "warnings": ["string"]
}
```

### 3. `inspect_symbol`
**Role**: unified symbol inspection for agents

#### Contract
```python
async def inspect_symbol(
        root_path: str,
        symbol_name: str,
        filename: str | None = None,
        line: int | None = None,
        include_references: bool = True,
        include_dependents: bool = False,
        max_references: int = 50,
) -> dict
```

#### Required Behavior
- Return the best structural definition candidates and, when requested, references.
- Prefer exact structural matches over semantic or heuristic matches.
- Keep exact facts separate from inferred or heuristic facts.
- Remain usable when embeddings are unavailable.

#### Response Shape
```json
{
    "status": "ok|degraded|error",
    "freshness": {},
    "symbol": "target symbol",
    "definitions": [
        {
            "file": "path/to/file.py",
            "startLine": 1,
            "endLine": 20,
            "language": "python",
            "confidence": "exact",
            "evidence": []
        }
    ],
    "references": [
        {
            "file": "path/to/caller.py",
            "line": 14,
            "kind": "call",
            "confidence": "high",
            "evidence": []
        }
    ],
    "warnings": ["string"]
}
```

### 4. `get_stats`
**Role**: repository orientation and hotspot detection

#### Contract
```python
async def get_stats(
    root_path: str,
    view: str = "code",
    include: str | None = None,
    exclude: str | None = None,
    roots: list[str] | None = None,
) -> dict
```

#### Required Behavior
- Default hotspot ranking to code-like source files rather than all tracked files.
- Support `code`, `tests`, and `all` views so source hotspots, test hotspots, and broader tracked-file views can be inspected separately.
- Support optional include and exclude globs plus optional root filters matched against project-relative paths.
- Report large files, large symbols, import fan-in hubs, import fan-out hubs, threshold violations, and direct test-gap candidates.
- Include a simple refactor-candidate ranking built from cheap structural metrics only.
- Report large non-code tracked files separately so they remain visible without polluting the default engineering hotspot list.
- Prefer fast structural data sources over semantic data sources.
- Include freshness metadata and trust warnings.

#### Response Shape
```json
{
    "status": "ok|missing|error",
    "summary": "human-readable summary",
    "freshness": {},
    "overview": {
        "trackedFiles": 0,
        "indexedSymbols": 0,
        "indexedImports": 0,
        "indexedEdges": 0,
        "languages": {
            "python": 0
        }
    },
    "hotspotScope": {
        "defaultView": "code",
        "view": "code",
        "filesConsidered": 0,
        "roots": ["src"],
        "include": "src/**",
        "exclude": "docs/**",
        "testFilesExcluded": 0,
        "nonCodeFilesExcluded": 0
    },
    "projectPulse": {
        "activeBranch": "main",
        "lastRefreshAt": "ISO-8601 timestamp or null",
        "lastScanType": "full|incremental|unknown"
    },
    "topLargeFiles": [
        {
            "file": "path/to/file.py",
            "loc": 220,
            "symbolCount": 8,
            "importCount": 5,
            "isTest": false
        }
    ],
    "nonCodeLargeFiles": [
        {
            "file": "docs/PROJECT_PLAN.md",
            "loc": 280,
            "kind": ".md",
            "reason": "Excluded from default hotspot ranking because it is not a code-like source file."
        }
    ],
    "largestSymbols": [
        {
            "symbol": "MyService.run",
            "file": "path/to/service.py",
            "kind": "function_definition",
            "loc": 61
        }
    ],
    "dependencyHubs": {
        "fanIn": [
            {
                "target": "path/to/module.py",
                "imports": 9,
                "scope": "internal"
            }
        ],
        "fanOut": [
            {
                "file": "path/to/file.py",
                "imports": 12
            }
        ]
    },
    "thresholdViolations": [
        {
            "rule": "file_loc",
            "file": "path/to/file.py",
            "actual": 220,
            "threshold": 200,
            "reason": "File exceeds the 200 line guideline."
        }
    ],
    "testGapCandidates": [
        {
            "file": "path/to/file.py",
            "loc": 220,
            "fanIn": 4,
            "fanOut": 8,
            "reason": "Large production file has no direct test match."
        }
    ],
    "refactorCandidates": [
        {
            "file": "path/to/file.py",
            "score": 0.82,
            "metrics": {
                "loc": 220,
                "fanIn": 4,
                "fanOut": 8,
                "testGap": 1
            },
            "reasons": ["high_loc", "import_hub", "missing_direct_test"]
        }
    ],
    "warnings": ["string"]
}
```

### 5. `impact_analysis`
**Role**: blast-radius and likely test-impact analysis

#### Contract
```python
async def impact_analysis(
        root_path: str,
        changed_files: list[str] | None = None,
        changed_symbols: list[str] | None = None,
        patch_text: str | None = None,
        include_tests: bool = True,
        max_results: int = 50,
) -> dict
```

#### Required Behavior
- Accept changed files, changed symbols, patch text, or a combination.
- Return affected symbols, dependent files, related tests, and explicit reasons.
- Separate exact structural impact from heuristic or enriched impact.
- Never present heuristic guesses as exact truth.

#### Response Shape
```json
{
    "status": "ok|degraded|error",
    "freshness": {},
    "summary": "human-readable summary",
    "affectedFiles": [
        {
            "file": "path/to/file.py",
            "confidence": "high",
            "reasons": ["imports changed symbol", "calls affected function"],
            "evidence": []
        }
    ],
    "affectedSymbols": [
        {
            "symbol": "MyService",
            "file": "path/to/service.py",
            "confidence": "high",
            "reasons": ["definition changed"],
            "evidence": []
        }
    ],
    "candidateTests": [
        {
            "file": "tests/test_service.py",
            "confidence": "medium",
            "reasons": ["related test heuristic", "imports affected module"],
            "evidence": []
        }
    ],
    "warnings": ["string"]
}
```

### 6. `enrich_analysis`
**Role**: scoped, expensive, framework-aware enrichment

#### Contract
```python
async def enrich_analysis(
        root_path: str,
        include: str | None = None,
        changed_files: list[str] | None = None,
        analyzers: list[str] | None = None,
        neighborhood_depth: int = 1,
        include_tests: bool = True,
) -> dict
```

#### Required Behavior
- This tool is opt-in and must not be required for baseline structural correctness.
- Accept a path-centered scope and optionally expand to nearby files through imports, dependents, or graph neighbors.
- Allow explicit analyzer selection such as `python_decorators`, `python_middleware`, `dependency_injection`, `route_registration`, and `test_impact`.
- Enriched inferred facts must remain distinguishable from exact structural facts.

#### Response Shape
```json
{
    "status": "ok|degraded|error",
    "freshness": {},
    "analyzersRun": ["python_middleware"],
    "filesAnalyzed": ["src/api.py"],
    "inferredFacts": [
        {
            "category": "middleware_chain",
            "subject": "AuthMiddleware",
            "confidence": "medium",
            "reason": "decorator and registration pattern detected",
            "evidence": []
        }
    ],
    "warnings": ["string"]
}
```

### 7. `search_code`
**Role**: semantic discovery and recall enhancement

#### Contract
```python
async def search_code(
        query: str,
        root_path: str,
        limit: int = 10,
        include: str | None = None,
        exclude: str | None = None,
) -> dict
```

#### Required Behavior
- Search remains valuable, but it is explicitly a secondary discovery layer.
- Search should use embeddings when available and literal fallback when needed.
- Search must not be the only path to useful answers during active refactors.

### 8. `find_definition` And `find_references`
**Role**: compatibility wrappers

#### Required Behavior
- Keep these tools for compatibility during the reboot.
- Implement them in terms of `inspect_symbol` where practical.
- Mark them as compatibility-oriented rather than the preferred long-term agent interface.

## Keep, Rename, And Deprecate Guidance

### Keep As Primary
- `refresh_index`
- `get_stats`

### Add As New Primary
- `get_index_status`
- `inspect_symbol`
- `impact_analysis`
- `enrich_analysis`

### Keep As Secondary
- `search_code`

### Keep For Compatibility, Then Reevaluate
- `find_definition`
- `find_references`

## Acceptance Criteria For The Reboot

- Partial refresh is materially cheaper than the current hash-every-file behavior on large repositories.
- Stale graph edges no longer survive common incremental refactor workflows.
- Structural tools remain usable without waiting for embeddings.
- Agents can check trust and freshness explicitly through `get_index_status`.
- Impact analysis produces better first-pass blast-radius guidance than raw search alone.

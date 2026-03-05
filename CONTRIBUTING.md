# Contributing to Code Intelligence

Thank you for your interest in contributing to Code Intelligence! This project aims to provide high-performance, AST-aware code intelligence for AI agents.

## 🛠️ Development Setup

This project uses `uv` for dependency management and project isolation.

1.  **Clone the Repository**:
    ```bash
    git clone https://github.com/nairraf/code-intel.git
    cd code-intel
    ```
2.  **Synchronize Environment**:
    ```bash
    uv sync --all-extras --dev
    ```
3.  **Local Indexing Dependencies**:
    Ensure [Ollama](https://ollama.com) is installed and running, then pull the required model:
    ```bash
    ollama pull unclemusclez/jina-embeddings-v2-base-code
    ```

## 🧪 Development Workflow

### Atomic Tasks & Commits
We follow a strict **Contract-First & Test-Gated** methodology:

*   **Atomic Changes**: Each PR or commit should focus on a single logical unit of work.
*   **Conventional Commits**: Use the [Conventional Commits](https://www.conventionalcommits.org/) specification (e.g., `feat(search): add fuzzy matching`, `fix(linker): resolve path normalization`).

### Testing & Quality Gates
*   **Test-Ready Architecture**: Use Dependency Injection for all services to ensure business logic is mockable.
*   **Coverage Mandate**: All new features must maintain a minimum of **80% unit test coverage**.
*   **Run Tests**:
    ```bash
    uv run pytest tests/ --cov=src
    ```

### Code Standards
*   **The 200/50 Rule**: Proactively split files exceeding 200 lines or complex methods exceeding 50 lines. One responsibility per file.
*   **Aggressive DRY**: Abstract patterns into shared utilities in `src/shared` (if applicable) or standardized helpers.

## 🚀 Pull Request Process

1.  Create a feature branch from `develop`.
2.  Ensure tests pass and coverage meets the 80% threshold.
3.  Update documentation (`docs/`, `README.md`) if your change affects usage.
4.  Open a PR against the `develop` branch.

## 🛡️ Security

Prior to submitting a PR, perform a basic security scan for:
*   Secret exposure.
*   Injection vulnerabilities (SQLi, Path Traversal) especially in vector filtering or file access logic.
*   Safe deserialization.

For professional vulnerability reporting, please refer to our [Security Policy](SECURITY.md).

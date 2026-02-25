# Code Intelligence MCP Server 🧠

Give your AI agents a "brain" that actually understands your codebase. This Model Context Protocol (MCP) server provides high-performance semantic search and deep code insights, making it easier for AI tools to navigate, understand, and modify complex projects.

**This is not just a search tool; it is an analysis engine.** While standard Indexers just treat files as pure text, `code-intel` parses your codebase into a living knowledge graph. It maps abstract syntax trees (ASTs), dynamic dependencies, and architectural patterns, allowing your AI to enforce strict methodologies, understand blast radiuses, and confidently pair-program on enterprise-grade software.

---

## 🚀 Get Started

The server requires **Ollama** to handle local embeddings.

1.  **Install & Download Model**:
    Download [Ollama](https://ollama.com) and pull the high-precision embedding model:
    ```bash
    ollama pull unclemusclez/jina-embeddings-v2-base-code
    ```
2.  **Add to MCP Configuration**:
    Add the following to your AI client's MCP settings (e.g., Claude Desktop or Antigravity `mcp_config.json`). Replace `/path/to/code-intel` with the absolute path to this project.
    
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
3.  **Use it!** Your AI assistant will automatically connect to Ollama and begin indexing your project upon the first query.

---

## 🎯 Unique Advantages for Structured Engineering

While many tools offer basic semantic search, `code-intel` is purpose-built to enforce strict architectural rules and support advanced software engineering methodologies:

*   **Project Pulse & Health Metrics**: Go beyond simple search. The internal engine actively identifies "Dependency Hubs" and "High-Risk Symbols" (files with high complexity but low test coverage), guiding refactoring efforts and enforcing test-gated workflows.
*   **Deep Framework Analysis**: Standard indexers often fail at mapping dynamic patterns. This server specifically tracks dynamic dependency injection (like Python's `Depends()`) and framework-specific middleware, allowing developers to keep business logic pure and fully mockable.
*   **Targeted Re-Indexing**: Working in a massive mono-repo? You don't need to re-index the entire universe. Use targeted `include`/`exclude` patterns to update the knowledge graph on-the-fly for only the microservice or module you are actively developing.
*   **Contract-First Validation**: By exposing the precise call graph and interface definitions, `code-intel` helps validate that implementations adhere to established API contracts and structural patterns before code is committed.

---

## � Why Code Intelligence?

AI models often struggle with large codebases because they can't "see" everything at once. This server acts as a **smart bridge**, solving several key challenges:

*   **Token Savings**: Instead of dumping your entire codebase into a Cloud AI's context (which is expensive and slow), this server finds the *exact* relevant snippets.
*   **Smarter Context**: Locates code by meaning, not just keywords, ensuring the AI gets the context it actually needs.
*   **Deep Relationships**: Maps how your code is connected—calls, definitions, and module interactions—so the AI can trace logic across files.
*   **Superior Code Embeddings**: Optimized for `jina-embeddings-v2-base-code`, which provides high-precision retrieval for 80+ programming languages.
*   **Cost & Speed Efficiency**: Local embedding caching prevents redundant processing, saving time and compute resources.

---

## ✨ Key Features

### ⚡ Intelligent Caching
Our embedding cache drastically reduces latency. By storing "fingerprints" of your code locally, we avoid re-calculating embeddings for unchanged files, making searches nearly instantaneous.

### 🧭 Semantic "Meaning-Based" Search
Go beyond simple keyword matching. Search for concepts like "how do we handle user authentication?" and find the relevant logic even if the exact words aren't used.

### 🏛️ Cross-File Architecture Graph
A persistent knowledge graph tracks imports and function calls across your entire project. This enables precise "Jump to Definition" and "Find References" that work reliably across many files, including advanced structural tracking for Dart widget instantiations and Python dependency injection (`Depends()`).

---

## �🛠️ Tools for Cloud AI

These tools are specifically designed to give Cloud-based AI agents "Just-in-Time" knowledge without bloating their memory.

| Tool | Benefit to Cloud AI |
|:---|:---|
| `search_code` | **Token Saver**: Feeds the AI only the specific logic it needs to solve a task. |
| `get_stats` | **Strategic Overview**: Identifies "Dependency Hubs" (critical files) and "High-Risk" areas without the AI needing to read every file. |
| `find_definition` | **Precise Navigation**: Allows the AI to jump straight to the source of any mystery function or variable. |
| `find_references` | **Impact Analysis**: Helps the AI understand the side-effects of a change before it happens. Includes advanced mapping for UI frameworks and backend routing. |
| `refresh_index` | **Real-time Sync**: Keeps the AI's internal "map" of your project up to date with your latest changes. |

---

## 🌟 New Features

Here are some of the advanced features we've recently added that Cloud AI agents can leverage directly:

### 🔎 Scope Tuning
Reduce noise by filtering what gets indexed and searched. Code-Intel supports standard glob patterns for exclusions and inclusions during search or re-indexing.

- **`search_code(query, include, exclude)`**: Semantic search with regex/glob filtering.
  - *Example*: `search_code("auth", exclude="tests/**")`
- **`refresh_index(include, exclude)`**: Target specific directories or exclude legacy code during re-indexing.
  - *Example*: `refresh_index(include="src/api/**")`

> **Note**: System directories like `node_modules`, `.git`, `venv`, and `__pycache__` are always excluded by default.

### 🔗 Advanced Symbol Resolution & Source Prioritization
We've supercharged how cross-file calls are analyzed:
- **Deep Language Integration**: High-confidence resolution of dynamic patterns like Python dependency injection (`Depends()`) and advanced Dart widget usage querying.
- **Language Scoping**: Smarter source prioritization ensures the AI surfaces the defining logic over secondary usages and tests.
- **Two-Pass Linking**: A complete refactor of the underlying linker provides bullet-proof symbol tracking across large codebases.

### 💾 Persistent Embedding Cache
A robust, local caching mechanism that persists embeddings across sessions, drastically reducing latency and compute overhead when restarting the server or performing small incremental updates.

### 🗄️ Internal Storage & Model Intelligence

The server manages its own local "vault" and uses local AI to power its semantic capabilities.

| Component | Default Location | Description |
|:---|:---|:---|
| **Intelligence Model** | `jina-embeddings-v2-base-code` | High-precision code embedding model (via Ollama). |
| **Central Vault** | `~/.code_intel_store/` | Where all project indexes, knowledge graphs, and local caches are stored. |
| **Emission Logs** | `~/.code_intel_store/logs/` | Detailed server logs for debugging and monitoring pulse. |

---

## 🛡️ Security & Quality Hardened
Independently audited and remediated against OWASP Top 10 vulnerabilities. Includes robust sanitization for vector filters, safe JSON-based serialization, and strict path containment. The codebase has also undergone a comprehensive quality review with an established remediation backlog.

---

## 🧪 Development

To run the test suite and ensure everything is working correctly:

```bash
uv run pytest tests/
```

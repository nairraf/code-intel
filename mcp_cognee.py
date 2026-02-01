import os
import sys
import warnings
import asyncio
import logging
import json
from pathlib import Path
from dotenv import load_dotenv
from contextlib import asynccontextmanager

# --- STAGE 0: ULTIMATE STDOUT PROTECTION (THE FORTRESS) ---
# 1. Save the TRUE stdout destination before any library touches it
_real_stdout_fd = os.dup(1)
# Create a private binary stream to the original stdout for the MCP protocol ONLY
_mcp_output_buffer = os.fdopen(_real_stdout_fd, "wb", buffering=0)

# 2. SEVER: Redirect fd 1 (raw stdout) to fd 2 (stderr) at the OS level
# This catches C-level printf, system calls, and any rogue fd 1 writes.
os.dup2(2, 1)

# 3. SEAL: Redirect Python's sys.stdout to sys.stderr
# This catches all Python print() and sys.stdout.write() calls.
_real_stdout_obj = sys.stdout 
sys.stdout = sys.stderr

# 4. SILENCE: Disable warnings and noisy environment variables
warnings.filterwarnings("ignore")
os.environ["TOKENIZERS_PARALLELISM"] = "false"
os.environ["COGNEE_DISABLE_UPDATE_CHECK"] = "True"
os.environ["COGNEE_SKIP_UPDATE_CHECK"] = "True"
os.environ["HUGGINGFACE_TOKENIZER"] = os.environ.get("HUGGINGFACE_TOKENIZER", "Qwen/Qwen2.5-Coder-7B")

# Silence ALL loggers immediately
logging.basicConfig(level=logging.ERROR, stream=sys.stderr)
for logger_name in ["asyncio", "anyio", "httpcore", "httpx", "urllib3", "cognee", "instructor", "fastmcp", "docket"]:
    logging.getLogger(logger_name).setLevel(logging.ERROR)

# --- EARLY CONFIGURATION ---
DEFAULT_VAULT_NAME = ".cognee_vault"
DEFAULT_LOGS_DIR_NAME = "logs"

def find_project_identity(search_path: str = None):
    """Finds project root by looking for markers."""
    current_path = Path(search_path or os.getcwd()).resolve()
    project_root = current_path
    markers = [".git", "pubspec.yaml", ".env", "pyproject.toml", "package.json"]
    for parent in [current_path] + list(current_path.parents):
        if any((parent / marker).exists() for marker in markers):
            project_root = parent
            break
    
    pubspec = project_root / "pubspec.yaml"
    if pubspec.exists():
        try:
            with open(pubspec, "r") as f:
                for line in f:
                    if line.startswith("name:"):
                        return line.split(":")[1].strip(), project_root
        except: pass
    
    package_json = project_root / "package.json"
    if package_json.exists():
        try:
            with open(package_json, "r") as f:
                data = json.load(f)
                if "name" in data:
                    return data["name"], project_root
        except: pass

    return project_root.name.strip(), project_root

def switch_log_file(project_id: str, logs_dir: Path):
    """Isolates logs to project-specific files."""
    from cognee.shared.logging_utils import PlainFileHandler
    root_logger = logging.getLogger()
    handlers_to_remove = []
    for handler in root_logger.handlers:
        if isinstance(handler, logging.FileHandler):
            handler.close()
            handlers_to_remove.append(handler)
    for handler in handlers_to_remove:
        root_logger.removeHandler(handler)
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file_path = logs_dir / f"{project_id}.log"
    try:
        new_handler = PlainFileHandler(str(log_file_path), encoding="utf-8")
        new_handler.setLevel(logging.DEBUG)
        root_logger.addHandler(new_handler)
    except Exception as e:
        sys.stderr.write(f"❌ Failed to switch log file: {e}\n")

# --- BOOTSTRAP ENVIRONMENT ---
try:
    _bootstrap_id, _bootstrap_root = find_project_identity(os.path.dirname(os.path.abspath(__file__)))
    _bootstrap_vault = _bootstrap_root / DEFAULT_VAULT_NAME
    _bootstrap_vault.mkdir(parents=True, exist_ok=True)
    _central_logs_dir = _bootstrap_root / DEFAULT_LOGS_DIR_NAME
    os.environ["SYSTEM_ROOT_DIRECTORY"] = str(_bootstrap_vault / ".cognee_system")
    os.environ["DATA_ROOT_DIRECTORY"] = str(_bootstrap_vault / ".data_storage")
    os.environ["COGNEE_LOGS_DIR"] = str(_central_logs_dir)
    os.environ["COGNEE_SYSTEM_PATH"] = str(_bootstrap_vault)
    os.environ["LOG_FILE_NAME"] = str(_central_logs_dir / f"{_bootstrap_id}.log")
except Exception as e:
    sys.stderr.write(f"⚠️ Bootstrap failed: {str(e)}\n")

load_dotenv(override=False)

# --- SCHEMA GUARDRAILS (MONKEYPATCHING) ---
def patch_data_models():
    """Robustness Patch: Adds aliases and defaults to Cognee's Pydantic models."""
    from pydantic import AliasChoices
    import cognee.shared.data_models as data_models
    try:
        if hasattr(data_models, "Node"):
            Node = data_models.Node
            Node.model_fields["id"].validation_alias = AliasChoices("id", "node_id", "identifier")
            Node.model_fields["name"].validation_alias = AliasChoices("name", "label", "title")
            Node.model_fields["name"].default = "Unknown"
            Node.model_fields["type"].validation_alias = AliasChoices("type", "category", "kind", "class")
            Node.model_fields["type"].default = "Entity"
            Node.model_fields["description"].validation_alias = AliasChoices("description", "desc", "summary")
            Node.model_fields["description"].default = ""
            Node.model_rebuild(force=True)
        if hasattr(data_models, "Edge"):
            Edge = data_models.Edge
            Edge.model_fields["source_node_id"].validation_alias = AliasChoices("source_node_id", "src_node_id", "from_id", "source")
            Edge.model_fields["target_node_id"].validation_alias = AliasChoices("target_node_id", "dst_node_id", "to_id", "target")
            Edge.model_fields["relationship_name"].validation_alias = AliasChoices("relationship_name", "rel_name", "relation", "type")
            Edge.model_fields["relationship_name"].default = "related_to"
            Edge.model_rebuild(force=True)
        sys.stderr.write("[PATCH] Cognee Schema Guardrails Applied.\n")
    except Exception as e:
        sys.stderr.write(f"⚠️ Failed to apply schema guardrails: {e}\n")

patch_data_models()

# --- STAGE 1: MCP TRANSPORT MONKEYPATCH ---
import mcp.server.stdio as mcp_stdio
from io import TextIOWrapper
import anyio

_orig_stdio_server = mcp_stdio.stdio_server

@asynccontextmanager
async def patched_stdio_server(stdin=None, stdout=None):
    """Forces the MCP server to use our protected private buffer instead of fd 1."""
    if not stdout:
        stdout = anyio.wrap_file(TextIOWrapper(_mcp_output_buffer, encoding="utf-8"))
    async with _orig_stdio_server(stdin=stdin, stdout=stdout) as (read_stream, write_stream):
        yield read_stream, write_stream

mcp_stdio.stdio_server = patched_stdio_server
sys.stderr.write("[PATCH] MCP Stdio Fortress Patch Applied.\n")

# --- IMPORTS ---
import cognee
from fastmcp import FastMCP
from cognee.modules.search.types import SearchType
import httpx

# --- MONKEYPATCHES ---
from cognee.infrastructure.databases.vector.embeddings.OllamaEmbeddingEngine import OllamaEmbeddingEngine
async def robust_get_embedding(self, prompt: str):
    import aiohttp
    payload = {"model": self.model, "prompt": prompt, "input": prompt, "options": {"num_ctx": 8192}}
    headers = {}
    api_key = os.getenv("LLM_API_KEY")
    if api_key: headers["Authorization"] = f"Bearer {api_key}"
    async with aiohttp.ClientSession() as session:
        endpoint = self.low_level_endpoint if hasattr(self, "low_level_endpoint") else self.endpoint
        async with session.post(endpoint, json=payload, headers=headers, timeout=60.0) as response:
            if response.status != 200:
                err_text = await response.text()
                raise Exception(f"Ollama error {response.status}: {err_text}")
            data = await response.json()
            if "data" in data and len(data["data"]) > 0: return data["data"][0]["embedding"]
            if "embeddings" in data: return data["embeddings"][0]
            if "embedding" in data: return data["embedding"]
            raise KeyError(f"Unexpected response format: {data}")

OllamaEmbeddingEngine._get_embedding = robust_get_embedding
sys.stderr.write("[PATCH] Cognee Ollama Compatibility Patch Applied.\n")

# Filters
WHITELIST_EXTENSIONS = {".py", ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".js", ".ts", ".tsx", ".jsx", ".css", ".html", ".sh", ".sql"}
SKIP_DIRECTORIES = {".git", ".venv", "venv", "__pycache__", "node_modules", "build", "dist", "bge-m3", ".cognee_vault", "logs"}
SKIP_FILES = {"uv.lock", "package-lock.json", "poetry.lock"}

mcp = FastMCP("CogneeMemory")

async def check_ollama():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:11434/api/tags", timeout=5.0)
            return response.status_code == 200
    except: return False

def load_cognee_context(search_path: str = None):
    p_id, p_root = find_project_identity(search_path)
    p_vault = p_root / DEFAULT_VAULT_NAME
    p_vault.mkdir(parents=True, exist_ok=True)
    os.environ["SYSTEM_ROOT_DIRECTORY"] = str(p_vault / ".cognee_system")
    os.environ["DATA_ROOT_DIRECTORY"] = str(p_vault / ".data_storage")
    os.environ["COGNEE_SYSTEM_PATH"] = str(p_vault)
    try:
        cognee.config.system_root_directory(str(p_vault / ".cognee_system"))
        cognee.config.data_root_directory(str(p_vault / ".data_storage"))
        switch_log_file(p_id, _central_logs_dir)
        # Shield against any new loggers
        for name in logging.Logger.manager.loggerDict:
            l = logging.getLogger(name)
            if hasattr(l, "handlers"):
                l.handlers = [h for h in l.handlers if not (isinstance(h, logging.StreamHandler) and h.stream in [_real_stdout_obj, sys.__stdout__])]
        logging.getLogger().handlers = [h for h in logging.getLogger().handlers if not (isinstance(h, logging.StreamHandler) and h.stream in [_real_stdout_obj, sys.__stdout__])]
    except Exception as e:
        sys.stderr.write(f"⚠️ Context switch failed: {str(e)}\n")
    return p_id, p_vault, p_root

@mcp.tool()
async def sync_project_memory(project_path: str = None):
    """Analyzes the current codebase and syncs it to the memory vault."""
    try:
        if not await check_ollama(): return "❌ Sync failed: Ollama is not running."
        p_id, _, p_root = load_cognee_context(project_path)
        files_to_add = []
        for root, dirs, files in os.walk(p_root):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRECTORIES and not d.startswith(".")]
            for file in files:
                if file in SKIP_FILES or file.startswith("."): continue
                file_path = Path(root) / file
                if file_path.suffix.lower() in WHITELIST_EXTENSIONS: files_to_add.append(str(file_path))
        if not files_to_add: return "⚠️ No valid files found."
        await cognee.add(files_to_add, dataset_name=p_id)
        await cognee.cognify(chunks_per_batch = 1)
        return f"✅ Memory synced for '{p_id}' ({len(files_to_add)} files)."
    except Exception as e:
        import traceback
        sys.stderr.write(traceback.format_exc())
        return f"❌ Sync error: {str(e)}"

@mcp.tool()
async def search_memory(query: str, search_type: str = "GRAPH_COMPLETION", project_path: str = None):
    """Searches project memory (GRAPH_COMPLETION or CODE)."""
    try:
        load_cognee_context(project_path)
        if not await check_ollama(): return "❌ Search failed: Ollama offline."
        s_type = getattr(SearchType, search_type.upper(), SearchType.GRAPH_COMPLETION)
        results = await cognee.search(query_text=query, query_type=s_type)
        return results if results else "No results found."
    except Exception as e: return f"❌ Search error: {str(e)}"

@mcp.tool()
async def check_memory_status(project_path: str = None):
    """Returns the current project status, storage size, and active configuration."""
    try:
        active_id, vault, root = load_cognee_context(project_path)
        total_size = file_count = 0
        if vault.exists():
            for f in vault.rglob("*"):
                if f.is_file():
                    total_size += f.stat().st_size
                    file_count += 1
        return {
            "project_identity": active_id,
            "vault_path": str(vault),
            "vault_size_mb": round(total_size / (1024 * 1024), 2),
            "internal_file_count": file_count,
            "ollama_status": "Online" if await check_ollama() else "Offline",
            "active_model": os.environ.get("LLM_MODEL"),
            "embedding_model": os.environ.get("EMBEDDING_MODEL")
        }
    except Exception as e: return f"❌ Status error: {str(e)}"

@mcp.tool()
async def prune_memory(project_path: str = None):
    """Clears all local memory and forces database unlock."""
    try:
        p_id, p_vault, _ = load_cognee_context(project_path)
        lock_paths = [
            p_vault / ".cognee_system" / "databases" / "cognee_graph_kuzu" / ".lock",
            p_vault / ".cognee_system" / "databases" / "cognee_graph_kuzu" / "lock"
        ]
        for lp in lock_paths:
            if lp.exists():
                try: lp.unlink()
                except: pass
        await cognee.prune.prune_system(metadata=True, cache=True)
        await cognee.prune.prune_data()
        return f"🧹 Memory pruned and locks cleared for '{p_id}'."
    except Exception as e: return f"❌ Prune failed: {str(e)}"

if __name__ == "__main__":
    if os.name == "nt": asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    mcp.run(show_banner=False)
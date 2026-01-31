import os
import sys
import contextlib
import logging
from pathlib import Path
import json
from dotenv import load_dotenv

# --- PREVENT STDOUT LEAKAGE ---
# This filter is the last line of defense for the MCP protocol.
class ProtocolFilter:
    def __init__(self, original_stdout, backup_stderr):
        self.stdout = original_stdout
        self.stderr = backup_stderr

    def write(self, data):
        if not data:
            return
        stripped = data.strip()
        # Only allow JSON messages or empty/newline noise if it looks like JSON structure
        if (stripped.startswith("{") and stripped.endswith("}")) or \
           (stripped.startswith('{"jsonrpc"') or stripped.startswith('{"id"')):
            self.stdout.write(data)
        else:
            self.stderr.write(data)

    def flush(self):
        self.stdout.flush()

    def __getattr__(self, name):
        return getattr(self.stdout, name)

# Apply the filter globally as early as possible
_original_stdout = sys.stdout
sys.stdout = ProtocolFilter(_original_stdout, sys.stderr)

# Silence noisy loggers
for logger_name in ["asyncio", "anyio", "httpcore", "httpx", "urllib3"]:
    logging.getLogger(logger_name).setLevel(logging.ERROR)

# --- EARLY CONFIGURATION ---
CENTRAL_MEMORY_VAULT = Path("D:/Development/ALL_COGNEE_MEMORIES")
CENTRAL_MEMORY_VAULT.mkdir(parents=True, exist_ok=True)

def find_project_identity():
    current_path = Path(os.getcwd()).resolve()
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

project_id, project_root = find_project_identity()

# Load env
root_env = project_root / ".env"
if root_env.exists():
    load_dotenv(root_env, override=True)

# Forced GPU/Ollama defaults
os.environ["LLM_PROVIDER"] = "ollama"
os.environ["LLM_MODEL"] = "qwen2.5-coder:7b"
os.environ["LLM_ENDPOINT"] = "http://localhost:11434/v1"
os.environ["EMBEDDING_PROVIDER"] = "ollama"
os.environ["EMBEDDING_MODEL"] = "qwen3-embedding:0.6b"
os.environ["EMBEDDING_ENDPOINT"] = "http://localhost:11434/api/embeddings"
os.environ["EMBEDDING_DIMENSIONS"] = "1024"
if not os.environ.get("HUGGINGFACE_TOKENIZER"):
    os.environ["HUGGINGFACE_TOKENIZER"] = "Qwen/Qwen2.5-Coder-7B"

# Paths
vault_path = CENTRAL_MEMORY_VAULT / project_id
os.environ["SYSTEM_ROOT_DIRECTORY"] = str(vault_path / ".cognee_system")
os.environ["DATA_ROOT_DIRECTORY"] = str(vault_path / ".data_storage")
os.environ["COGNEE_LOGS_DIR"] = str(vault_path / "logs")
os.environ["COGNEE_SYSTEM_PATH"] = str(vault_path)

# --- IMPORTS ---
import asyncio
import cognee
from fastmcp import FastMCP
from cognee.modules.search.types import SearchType
import httpx

# --- MONKEYPATCH ---
from cognee.infrastructure.databases.vector.embeddings.OllamaEmbeddingEngine import OllamaEmbeddingEngine
async def robust_get_embedding(self, prompt: str):
    import aiohttp
    payload = {
        "model": self.model, "prompt": prompt, "input": prompt,
        "options": {"num_ctx": 8192}
    }
    headers = {}
    api_key = os.getenv("LLM_API_KEY")
    if api_key: headers["Authorization"] = f"Bearer {api_key}"
    async with aiohttp.ClientSession() as session:
        async with session.post(self.endpoint, json=payload, headers=headers, timeout=60.0) as response:
            if response.status != 200:
                err_text = await response.text()
                raise Exception(f"Ollama error {response.status}: {err_text}")
            data = await response.json()
            if "data" in data and len(data["data"]) > 0: return data["data"][0]["embedding"]
            if "embeddings" in data: return data["embeddings"][0]
            if "embedding" in data: return data["embedding"]
            raise KeyError(f"Unexpected response format: {data}")

OllamaEmbeddingEngine._get_embedding = robust_get_embedding
sys.stderr.write("🛠️ Cognee Ollama Compatibility Patch Applied.\n")

# Filters
WHITELIST_EXTENSIONS = {".py", ".md", ".txt", ".json", ".yaml", ".yml", ".toml", ".js", ".ts", ".tsx", ".jsx", ".css", ".html", ".sh", ".sql"}
SKIP_DIRECTORIES = {".git", ".venv", "venv", "__pycache__", "node_modules", "build", "dist", "bge-m3"}
SKIP_FILES = {"uv.lock", "package-lock.json", "poetry.lock"}

mcp = FastMCP("CogneeMemory")

async def check_ollama():
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get("http://localhost:11434/api/tags", timeout=5.0)
            return response.status_code == 200
    except: return False

def load_cognee_context():
    """Returns the pre-initialized Cognee context."""
    project_vault_path = CENTRAL_MEMORY_VAULT / project_id
    return project_id, project_vault_path, project_root

@mcp.tool()
async def sync_project_memory():
    """Analyzes the current codebase and syncs it to the memory vault."""
    # We use a nested function to ensure return values are captured AFTER redirection ends
    async def run_sync():
        with contextlib.redirect_stdout(sys.stderr):
            if not await check_ollama():
                return "❌ Sync failed: Ollama is not running."
            
            files_to_add = []
            for root, dirs, files in os.walk(project_root):
                dirs[:] = [d for d in dirs if d not in SKIP_DIRECTORIES and not d.startswith(".")]
                for file in files:
                    if file in SKIP_FILES or file.startswith("."): continue
                    file_path = Path(root) / file
                    if file_path.suffix.lower() in WHITELIST_EXTENSIONS:
                        files_to_add.append(str(file_path))
            
            if not files_to_add: return "⚠️ No valid files found."
            
            await cognee.add(files_to_add, dataset_name=project_id)
            await cognee.cognify(chunks_per_batch = 1)
            return f"✅ Memory synced for '{project_id}' ({len(files_to_add)} files)."
    
    try:
        return await run_sync()
    except Exception as e:
        return f"❌ Sync error: {str(e)}"

@mcp.tool()
async def search_memory(query: str, search_type: str = "GRAPH_COMPLETION"):
    """Searches project memory (GRAPH_COMPLETION or CODE)."""
    async def run_search():
        with contextlib.redirect_stdout(sys.stderr):
            if not await check_ollama(): return "❌ Search failed: Ollama offline."
            s_type = getattr(SearchType, search_type.upper(), SearchType.GRAPH_COMPLETION)
            results = await cognee.search(query_text=query, query_type=s_type)
            return results if results else "No results found."
    return await run_search()

@mcp.tool()
async def check_memory_status():
    """Returns the current project status, storage size, and active configuration."""
    with contextlib.redirect_stdout(sys.stderr):
        active_id, vault, root = load_cognee_context()
        
        # Calculate vault metrics
        total_size = 0
        file_count = 0
        if vault.exists():
            for f in vault.rglob("*"):
                if f.is_file():
                    total_size += f.stat().st_size
                    file_count += 1
        
        online = await check_ollama()
        return {
            "project_identity": active_id,
            "vault_path": str(vault),
            "vault_size_mb": round(total_size / (1024 * 1024), 2),
            "internal_file_count": file_count,
            "ollama_status": "Online" if online else "Offline",
            "active_model": os.environ.get("LLM_MODEL"),
            "embedding_model": os.environ.get("EMBEDDING_MODEL"),
            "chunk_size": os.environ.get("CHUNK_SIZE", "2048")
        }

@mcp.tool()
async def prune_memory():
    """Clears all local memory for the project."""
    async def run_prune():
        with contextlib.redirect_stdout(sys.stderr):
            await cognee.prune.prune_system(metadata=True)
            await cognee.prune.prune_data()
            return f"🧹 Memory pruned for '{project_id}'."
    return await run_prune()

if __name__ == "__main__":
    if os.name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(check_ollama())
    mcp.run()
import asyncio
import subprocess
import logging
from typing import Dict, Optional, List, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

async def is_git_repo(root: str) -> bool:
    """Check if the given directory is inside a git repository."""
    try:
        process = await asyncio.create_subprocess_exec(
            "git", "rev-parse", "--is-inside-work-tree",
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=5)
        return process.returncode == 0 and stdout.decode().strip() == "true"
    except Exception:
        return False

async def get_file_git_info(filepath: str, repo_root: str) -> Dict[str, Optional[str]]:
    """
    Get git metadata for a single file asynchronously.
    """
    try:
        process = await asyncio.create_subprocess_exec(
            "git", "log", "-1", "--format=%an|%ai", "--", filepath,
            cwd=repo_root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=10)
        
        if process.returncode == 0:
            output = stdout.decode().strip()
            if output:
                parts = output.split("|", 1)
                if len(parts) == 2:
                    return {"author": parts[0].strip(), "last_modified": parts[1].strip()}
    except Exception as e:
        logger.debug(f"Git info lookup failed for {filepath}: {e}")

    return {"author": None, "last_modified": None}

async def batch_get_git_info(filepaths: list, repo_root: str) -> Dict[str, Dict[str, Optional[str]]]:
    """
    Get git metadata for a list of files in parallel, limited by a semaphore.
    """
    if not await is_git_repo(repo_root):
        return {fp: {"author": None, "last_modified": None} for fp in filepaths}

    # Strict limit on concurrent git subprocesses to prevent Windows "hangs"
    semaphore = asyncio.Semaphore(10)

    async def _bounded_get(fp):
        async with semaphore:
            return fp, await get_file_git_info(fp, repo_root)

    tasks = [_bounded_get(fp) for fp in set(filepaths)]
    wrapped_results = await asyncio.gather(*tasks)
    return {fp: info for fp, info in wrapped_results}

import asyncio
import subprocess
import logging
import os
from typing import Dict, Optional, List, Tuple
from pathlib import Path
import traceback

logger = logging.getLogger(__name__)

async def is_git_repo(root: str) -> bool:
    """Check if the given directory is inside a git repository."""
    try:
        process = await asyncio.create_subprocess_exec(
            "git", "rev-parse", "--is-inside-work-tree",
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30)
        is_repo = process.returncode == 0 and stdout.decode().strip() == "true"
        if not is_repo:
            err = stderr.decode().strip()
            logger.info(f"Directory {root} is not in a git work tree. Git log: {err}")
        return is_repo
    except asyncio.TimeoutError:
        logger.warning(f"Git repo check timed out for {root}. Falling back to .git directory check.")
        try:
            process.kill()
            await asyncio.wait_for(process.wait(), timeout=2)
        except:
            pass
        # Fallback: check if .git exists directly
        git_dir = Path(root) / ".git"
        return git_dir.exists() and git_dir.is_dir()
    except Exception:
        logger.error(f"Error checking git repo status for {root}:\n{traceback.format_exc()}")
        return False

async def get_file_git_info(filepath: str, repo_root: str) -> Dict[str, Optional[str]]:
    """
    Get git metadata for a single file asynchronously.
    """
    try:
        # Crucial for Windows: ensure both paths are resolved and same-case for relpath
        abs_repo = str(Path(repo_root).resolve())
        abs_file = str(Path(filepath).resolve())
        rel_path = os.path.relpath(abs_file, abs_repo)
        
        process = await asyncio.create_subprocess_exec(
            "git", "log", "-1", "--format=%an|%ai", "--", rel_path,
            cwd=abs_repo,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            stdin=subprocess.DEVNULL,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=10)
        
        if process.returncode == 0:
            output = stdout.decode().strip()
            if output:
                parts = output.split("|", 1)
                if len(parts) == 2:
                    return {"author": parts[0].strip(), "last_modified": parts[1].strip()}
            else:
                logger.info(f"Git log returned no output for: {rel_path} (File may be untracked)")
        else:
            err_msg = stderr.decode().strip()
            logger.warning(f"Git log failed for {rel_path} (return code {process.returncode}): {err_msg}")
    except asyncio.TimeoutError:
        logger.warning(f"Git info lookup timed out for {filepath}")
        try:
            process.kill()
            await asyncio.wait_for(process.wait(), timeout=2)
        except:
            pass
    except Exception:
        logger.error(f"Git info lookup exception for {filepath}:\n{traceback.format_exc()}")

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

async def get_active_branch(repo_root: str) -> str:
    """Get the current active branch name."""
    def _get_branch():
        try:
            abs_repo = str(Path(repo_root).resolve())
            result = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=abs_repo,
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return "unknown"

    return await asyncio.to_thread(_get_branch)

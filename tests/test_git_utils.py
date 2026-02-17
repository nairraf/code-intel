import os
import tempfile
import subprocess
import pytest
from pathlib import Path
from src.git_utils import is_git_repo, get_file_git_info, batch_get_git_info

@pytest.mark.asyncio
async def test_is_git_repo():
    with tempfile.TemporaryDirectory() as tmpdir:
        assert not await is_git_repo(tmpdir)
        subprocess.run(["git", "init"], cwd=tmpdir, check=True, capture_output=True)
        assert await is_git_repo(tmpdir)

@pytest.mark.asyncio
async def test_get_file_git_info():
    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(["git", "init"], cwd=tmpdir, check=True, capture_output=True)
        test_file = Path(tmpdir) / "test.py"
        test_file.write_text("print('hi')\n")
        subprocess.run(["git", "add", "test.py"], cwd=tmpdir, check=True, capture_output=True)
        subprocess.run(["git", "-c", "user.name=Test", "-c", "user.email=test@example.com", "commit", "-m", "add test.py"], cwd=tmpdir, check=True, capture_output=True)
        info = await get_file_git_info(str(test_file), tmpdir)
        assert info["author"] == "Test"
        assert info["last_modified"] is not None

@pytest.mark.asyncio
async def test_get_file_git_info_untracked():
    with tempfile.TemporaryDirectory() as tmpdir:
        subprocess.run(["git", "init"], cwd=tmpdir, check=True, capture_output=True)
        test_file = Path(tmpdir) / "untracked.py"
        test_file.write_text("print('hi')\n")
        info = await get_file_git_info(str(test_file), tmpdir)
        assert info["author"] is None
        assert info["last_modified"] is None

@pytest.mark.asyncio
async def test_batch_get_git_info_non_git():
    with tempfile.TemporaryDirectory() as tmpdir:
        files = [str(Path(tmpdir) / f"file{i}.py") for i in range(2)]
        for f in files:
            Path(f).write_text("print('hi')\n")
        batch = await batch_get_git_info(files, tmpdir)
        for meta in batch.values():
            assert meta["author"] is None
            assert meta["last_modified"] is None

@pytest.mark.asyncio
async def test_is_git_repo_timeout_fallback(mocker):
    import asyncio
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a .git directory
        git_dir = Path(tmpdir) / ".git"
        git_dir.mkdir()
        
        # Mock asyncio.wait_for to raise TimeoutError
        mocker.patch("asyncio.wait_for", side_effect=asyncio.TimeoutError)
        
        # Should return True because .git directory exists
        assert await is_git_repo(tmpdir)

@pytest.mark.asyncio
async def test_is_git_repo_timeout_no_fallback(mocker):
    import asyncio
    with tempfile.TemporaryDirectory() as tmpdir:
        # No .git directory
        
        # Mock asyncio.wait_for to raise TimeoutError
        mocker.patch("asyncio.wait_for", side_effect=asyncio.TimeoutError)
        
        # Should return False because no .git directory
        assert not await is_git_repo(tmpdir)

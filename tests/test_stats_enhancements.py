
import pytest
from unittest.mock import MagicMock, patch
from src.tools.stats import get_stats_impl


@pytest.mark.asyncio
async def test_get_detailed_stats_enhancements():
    project_root = "/mock/project"

    mock_ctx = MagicMock()
    mock_ctx.vector_store.get_index_metadata.return_value = {
        "indexed_at": "2026-03-05T10:00:00Z",
        "commit_hash": "a1b2c3d",
        "is_dirty": False,
        "scan_type": "full",
        "model_name": "bge-m3"
    }

    mock_ctx.vector_store.get_detailed_stats.return_value = {
        "chunk_count": 100,
        "file_count": 10,
        "languages": {"python": 100},
        "avg_complexity": 5.0,
        "max_complexity": 15,
        "high_risk_symbols": [
            {"symbol": "risky_func", "complexity": 15, "file": "main.py"}
        ],
        "dependency_hubs": [
            {"file": "utils.py", "count": 10},
            {"file": "models.py", "count": 8}
        ],
        "test_gaps": [
            {"symbol": "risky_func", "complexity": 15, "file": "main.py"}
        ],
        "stale_files_count": 3,
        "rule_violations": [
            {"file": "large_file.py", "lines": 250, "rule": "200/50 Rule: File exceeds 200 lines"}
        ]
    }

    with patch('src.tools.stats.get_active_branch', return_value="feat/new-feature"), \
         patch('src.tools.stats.get_current_git_commit', return_value="f89a2b"), \
         patch('src.tools.stats.check_git_dirty', return_value=True):
         
        result = await get_stats_impl(project_root, ctx=mock_ctx)

        assert "Dependency Hubs" in result
        assert "utils.py (10 imports)" in result
        assert "Test Gaps" in result
        assert "risky_func (15)" in result
        assert "Rule Violations" in result
        assert "large_file.py" in result
        assert "Project Pulse:" in result
        assert "Active Branch:   feat/new-feature" in result
        assert "Stale Files:     3" in result
        assert "Freshness:       STALE" in result  # Because hashes don't match
        assert "f89a2b" in result


@pytest.mark.asyncio
async def test_get_active_branch():
    from src.git_utils import get_active_branch

    with patch('asyncio.create_subprocess_exec') as mock_exec:
        mock_process = MagicMock()

        async def mock_communicate():
            return b"main\n", b""

        mock_process.communicate = mock_communicate
        mock_process.returncode = 0
        mock_exec.return_value = mock_process

        branch = await get_active_branch(".")
        assert branch == "main"

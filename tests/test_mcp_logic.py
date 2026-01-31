import asyncio
import os
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys

# Add parent directory to path to import mcp_cognee
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import mcp_cognee

# Setup a dummy environment for testing
TEST_ROOT = Path("test_env_sandbox")
TEST_VAULT = Path("test_vault")

def setup_sandbox():
    if TEST_ROOT.exists():
        shutil.rmtree(TEST_ROOT)
    TEST_ROOT.mkdir()
    
    # Create fake project structure
    (TEST_ROOT / "my_cool_project").mkdir()
    (TEST_ROOT / "my_cool_project" / ".git").mkdir()
    
    # Create another one with pubspec
    (TEST_ROOT / "flutter_project").mkdir()
    with open(TEST_ROOT / "flutter_project" / "pubspec.yaml", "w") as f:
        f.write("name: super_app\ndescription: a test app\n")

    # Create one with package.json
    (TEST_ROOT / "node_project").mkdir()
    with open(TEST_ROOT / "node_project" / "package.json", "w") as f:
        f.write('{"name": "mcp-web-tool", "version": "1.0.0"}')

    # Mock the central vault path in the module
    mcp_cognee.CENTRAL_MEMORY_VAULT = TEST_VAULT

def teardown_sandbox():
    if TEST_ROOT.exists():
        shutil.rmtree(TEST_ROOT)
    if TEST_VAULT.exists():
        shutil.rmtree(TEST_VAULT)

async def test_identity_git():
    print("Testing Project Identity (Git)...")
    target_dir = (TEST_ROOT / "my_cool_project").resolve()
    
    with patch("os.getcwd", return_value=str(target_dir)):
        p_id, p_root = mcp_cognee.find_project_identity()
        print(f"  Result: ID='{p_id}', Root='{p_root}'", flush=True)
        print(f"  Expected: ID='my_cool_project', Root='{target_dir}'", flush=True)
        
        if p_id != "my_cool_project":
            raise AssertionError(f"ID mismatch: got '{p_id}', want 'my_cool_project'")
        if p_root.resolve() != target_dir:
            raise AssertionError(f"Root mismatch: got '{p_root.resolve()}', want '{target_dir}'")

async def test_identity_flutter():
    print("Testing Project Identity (Flutter/Pubspec)...")
    target_dir = (TEST_ROOT / "flutter_project").resolve()
    
    with patch("os.getcwd", return_value=str(target_dir)):

        p_id, p_root = mcp_cognee.find_project_identity()
        print(f"  Result: ID={p_id}, Root={p_root.name}")
        assert p_id == "super_app"
        assert p_root.resolve() == target_dir.resolve()

async def test_identity_node():
    print("Testing Project Identity (Node/package.json)...")
    target_dir = (TEST_ROOT / "node_project").resolve()
    with patch("os.getcwd", return_value=str(target_dir)):
        p_id, p_root = mcp_cognee.find_project_identity()
        print(f"  Result: ID='{p_id}', Root='{p_root}'")
        assert p_id == "mcp-web-tool"
        assert p_root.resolve() == target_dir.resolve()

async def test_identity_explicit_path():
    print("Testing Project Identity (Explicit Path)...")
    target_dir = (TEST_ROOT / "flutter_project").resolve()
    # We do NOT patch os.getcwd here, we pass the path directly
    p_id, p_root = mcp_cognee.find_project_identity(str(target_dir))
    print(f"  Result: ID='{p_id}', Root='{p_root}'")
    assert p_id == "super_app"
    assert p_root.resolve() == target_dir.resolve()

async def test_ollama_check():
    print("Testing Ollama Connection (Real)...")
    # This might fail if Ollama isn't running, but we want to know
    is_up = await mcp_cognee.check_ollama()
    print(f"  Ollama Status: {'UP' if is_up else 'DOWN'}")

async def main():
    setup_sandbox()
    try:
        await test_identity_git()
        await test_identity_flutter()
        await test_identity_node()
        await test_identity_explicit_path()
        await test_ollama_check()
        print("\n✅ All Logic Tests Passed!")
        with open("test_result.txt", "w") as f:
            f.write("PASS")
    except AssertionError as e:
        print(f"\n❌ Test Failed: {e}")
        with open("test_result.txt", "w") as f:
            f.write(f"FAIL: {e}")
    except Exception as e:
        print(f"\n❌ Unexpected Error: {e}")
        with open("test_result.txt", "w") as f:
            f.write(f"FAIL: {e}")
    finally:
        teardown_sandbox()

if __name__ == "__main__":
    if os.name == "nt":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())

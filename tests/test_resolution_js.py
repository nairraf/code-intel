import pytest
import os
import sys
import json
from pathlib import Path

# Add project root to sys.path to allow importing src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.resolution.javascript import JSImportResolver

@pytest.fixture
def mock_js_project(tmp_path):
    # Setup:
    # /project
    #   tsconfig.json
    #   src/
    #     index.ts
    #     components/
    #       Button.tsx
    #       Input/
    #         index.tsx
    #     utils/
    #       helpers.ts
    
    project_root = tmp_path / "project"
    project_root.mkdir()
    
    # Create tsconfig with paths
    tsconfig = {
        "compilerOptions": {
            "baseUrl": "./src",
            "paths": {
                "@/components/*": ["components/*"],
                "@/utils/*": ["utils/*"]
            }
        }
    }
    with open(project_root / "tsconfig.json", "w") as f:
        json.dump(tsconfig, f)
        
    (project_root / "src").mkdir()
    (project_root / "src" / "index.ts").touch()
    
    (project_root / "src" / "components").mkdir()
    (project_root / "src" / "components" / "Button.tsx").touch()
    
    (project_root / "src" / "components" / "Input").mkdir()
    (project_root / "src" / "components" / "Input" / "index.tsx").touch()
    
    (project_root / "src" / "utils").mkdir()
    (project_root / "src" / "utils" / "helpers.ts").touch()
    
    return project_root

def test_resolve_relative_extension_guessing(mock_js_project):
    resolver = JSImportResolver(str(mock_js_project))
    source = str(mock_js_project / "src" / "index.ts")
    
    # ./utils/helpers (implicit .ts)
    resolved = resolver.resolve(source, "./utils/helpers")
    assert resolved == str(mock_js_project / "src" / "utils" / "helpers.ts")

def test_resolve_directory_index(mock_js_project):
    resolver = JSImportResolver(str(mock_js_project))
    source = str(mock_js_project / "src" / "index.ts")
    
    # ./components/Input (should find index.tsx)
    resolved = resolver.resolve(source, "./components/Input")
    assert resolved == str(mock_js_project / "src" / "components" / "Input" / "index.tsx")

def test_resolve_tsconfig_alias(mock_js_project):
    resolver = JSImportResolver(str(mock_js_project))
    source = str(mock_js_project / "src" / "utils" / "helpers.ts")
    
    # @/components/Button -> src/components/Button.tsx
    # baseUrl is ./src, path is components/*
    resolved = resolver.resolve(source, "@/components/Button")
    assert resolved == str(mock_js_project / "src" / "components" / "Button.tsx")

def test_resolve_node_modules_ignored(mock_js_project):
    resolver = JSImportResolver(str(mock_js_project))
    source = str(mock_js_project / "src" / "index.ts")
    
    resolved = resolver.resolve(source, "react")
    assert resolved is None

def test_resolve_invalid_alias_path(mock_js_project):
    resolver = JSImportResolver(str(mock_js_project))
    source = str(mock_js_project / "src" / "utils" / "helpers.ts")
    
    # @/components/Missing -> should fail
    resolved = resolver.resolve(source, "@/components/Missing")
    assert resolved is None

def test_resolve_directory_without_index(mock_js_project):
    # Setup a directory without index
    (mock_js_project / "src" / "utils" / "empty_dir").mkdir()
    
    resolver = JSImportResolver(str(mock_js_project))
    source = str(mock_js_project / "src" / "index.ts")
    
    # ./utils/empty_dir -> fails if no index inside
    resolved = resolver.resolve(source, "./utils/empty_dir")
    assert resolved is None

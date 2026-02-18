import pytest
import os
import sys
from pathlib import Path

# Add project root to sys.path to allow importing src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.resolution.dart import DartImportResolver

@pytest.fixture
def mock_dart_project(tmp_path):
    # Setup:
    # /project
    #   pubspec.yaml
    #   lib/
    #     main.dart
    #     utils.dart
    #     models/
    #       user.dart
    
    project_root = tmp_path / "project"
    project_root.mkdir()
    
    # Create simple pubspec
    pubspec_content = """
name: my_app
description: A new Flutter project.
environment:
  sdk: ">=2.12.0 <3.0.0"
dependencies:
  flutter:
    sdk: flutter
"""
    with open(project_root / "pubspec.yaml", "w", encoding='utf-8') as f:
        f.write(pubspec_content)
        
    (project_root / "lib").mkdir()
    (project_root / "lib" / "main.dart").touch()
    (project_root / "lib" / "utils.dart").touch()
    
    (project_root / "lib" / "models").mkdir()
    (project_root / "lib" / "models" / "user.dart").touch()
    
    return project_root

def test_resolve_package_import(mock_dart_project):
    resolver = DartImportResolver(str(mock_dart_project))
    source = str(mock_dart_project / "lib" / "main.dart")
    
    # import 'package:my_app/utils.dart'
    # package_name is my_app, maps to lib/
    resolved = resolver.resolve(source, "package:my_app/models/user.dart")
    assert resolved == str(mock_dart_project / "lib" / "models" / "user.dart")

def test_resolve_relative_import(mock_dart_project):
    resolver = DartImportResolver(str(mock_dart_project))
    source = str(mock_dart_project / "lib" / "models" / "user.dart")
    
    # import '../utils.dart'
    resolved = resolver.resolve(source, "../utils.dart")
    assert resolved == str(mock_dart_project / "lib" / "utils.dart")

def test_resolve_external_package_returns_none(mock_dart_project):
    resolver = DartImportResolver(str(mock_dart_project))
    source = str(mock_dart_project / "lib" / "main.dart")
    
    # import 'package:flutter/material.dart'
    resolved = resolver.resolve(source, "package:flutter/material.dart")
    assert resolved is None

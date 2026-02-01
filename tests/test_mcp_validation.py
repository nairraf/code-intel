import pytest
import sys
import os

# Ensure the module can be imported
sys.path.append(os.getcwd())

import mcp_cognee
import cognee.shared.data_models as data_models

def test_node_validation_shield():
    """Verify Node model handles missing fields and aliases."""
    # Test missing fields (should use defaults)
    record = {"id": "test_id"} # Missing name, type, description
    node = data_models.Node(**record)
    assert node.id == "test_id"
    assert node.name == "Unknown"
    assert node.type == "Entity"
    assert node.description == ""

    # Test aliases
    record_with_aliases = {
        "node_id": "alias_id",
        "label": "My Node",
        "category": "Concept",
        "summary": "This is a summary"
    }
    node = data_models.Node(**record_with_aliases)
    assert node.id == "alias_id"
    assert node.name == "My Node"
    assert node.type == "Concept"
    assert node.description == "This is a summary"

def test_edge_validation_shield():
    """Verify Edge model handles aliases and default relationship names."""
    record = {
        "src_node_id": "A",
        "target": "B",
        # relationship_name missing
    }
    edge = data_models.Edge(**record)
    assert edge.source_node_id == "A"
    assert edge.target_node_id == "B"
    assert edge.relationship_name == "related_to"

    # Test another variation
    record_v2 = {
        "from_id": "C",
        "dst_node_id": "D",
        "rel_name": "connected"
    }
    edge = data_models.Edge(**record_v2)
    assert edge.source_node_id == "C"
    assert edge.target_node_id == "D"
    assert edge.relationship_name == "connected"

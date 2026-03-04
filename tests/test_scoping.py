import pytest
from unittest.mock import Mock
from src.scoping import get_scoping_strategy, PythonScopingStrategy, DartScopingStrategy, DefaultScopingStrategy

def test_get_scoping_strategy():
    assert isinstance(get_scoping_strategy("python"), PythonScopingStrategy)
    assert isinstance(get_scoping_strategy("dart"), DartScopingStrategy)
    assert isinstance(get_scoping_strategy("unknown"), DefaultScopingStrategy)

def create_mock_node(node_type, parent=None, end_byte=0, next_named_sibling=None):
    m = Mock()
    m.type = node_type
    m.parent = parent
    m.end_byte = end_byte
    m.next_named_sibling = next_named_sibling
    return m

def test_default_scoping_strategy():
    strategy = DefaultScopingStrategy()
    mock_node = create_mock_node("test", end_byte=100)
    
    assert strategy.is_global_target(mock_node) is False
    assert strategy.get_special_handling(mock_node) == (100, mock_node)

def test_python_scoping_strategy_global():
    strategy = PythonScopingStrategy()
    
    mock_module = create_mock_node("module")
    mock_expr = create_mock_node("expression_statement", parent=mock_module)
    mock_assign = create_mock_node("assignment", parent=mock_expr)
    assert strategy.is_global_target(mock_assign) is True
    
    mock_func = create_mock_node("function_definition", parent=mock_module)
    mock_expr2 = create_mock_node("expression_statement", parent=mock_func)
    mock_assign2 = create_mock_node("assignment", parent=mock_expr2)
    assert strategy.is_global_target(mock_assign2) is False

def test_dart_scoping_strategy_global():
    strategy = DartScopingStrategy()
    
    mock_prog = create_mock_node("program")
    mock_decl = create_mock_node("declaration", parent=mock_prog)
    assert strategy.is_global_target(mock_decl) is True
    
    mock_class = create_mock_node("class_definition", parent=mock_prog)
    mock_decl2 = create_mock_node("declaration", parent=mock_class)
    assert strategy.is_global_target(mock_decl2) is False

def test_dart_scoping_strategy_special_handling():
    strategy = DartScopingStrategy()
    
    mock_body = create_mock_node("function_body", end_byte=200)
    mock_sig = create_mock_node("function_signature", end_byte=100, next_named_sibling=mock_body)
    
    end_byte, usage_node = strategy.get_special_handling(mock_sig)
    assert end_byte == 200
    assert usage_node == mock_body

def test_python_scoping_strategy_special_handling():
    strategy = PythonScopingStrategy()
    
    mock_decorated = create_mock_node("decorated_definition")
    mock_func = create_mock_node("function_definition", parent=mock_decorated, end_byte=150)
    
    end_byte, usage_node = strategy.get_special_handling(mock_func)
    assert end_byte == 150
    assert usage_node == mock_decorated

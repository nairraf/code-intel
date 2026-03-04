import sys
from os.path import dirname, abspath, join

# Ensure project root is on sys.path so `src` is importable
root_dir = dirname(dirname(abspath(__file__)))
src_dir = join(root_dir, "src")
sys.path.insert(0, root_dir)  # allows `import src.context`
sys.path.append(src_dir)      # allows `from xyz import ...` (legacy style)

import pytest
import src.context as _ctx_module


@pytest.fixture(autouse=True)
def prime_app_context():
    """Ensure the AppContext singleton is initialised before each test.

    Calling `get_context()` sets `_context` to a real object so that
    `patch('src.context._context.vector_store', ...)` doesn't raise
    ``AttributeError: None does not have attribute 'vector_store'``.

    After each test the singleton is torn down so tests don't share state.
    """
    _ctx_module.get_context()
    yield
    _ctx_module._context = None

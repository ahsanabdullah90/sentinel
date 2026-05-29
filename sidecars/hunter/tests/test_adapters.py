import pytest
from src_py.adapters import resolve_adapter
from src_py.adapters.brightspyre import BrightspyreAdapter
from src_py.adapters.generic import GenericAdapter

def test_resolve_adapter_brightspyre():
    adapter = resolve_adapter("https://resume.brightspyre.com")
    assert isinstance(adapter, BrightspyreAdapter)

def test_resolve_adapter_generic():
    adapter = resolve_adapter("https://some-unknown-portal.com")
    assert isinstance(adapter, GenericAdapter)

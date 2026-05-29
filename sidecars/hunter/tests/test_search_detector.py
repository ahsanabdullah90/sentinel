import pytest
from src_py.utils.search_detector import detect_search_input

class MockPage:
    def __init__(self, js_result):
        self.js_result = js_result
    async def evaluate(self, js):
        return self.js_result

@pytest.mark.asyncio
async def test_detect_search_input():
    page = MockPage("#search-input")
    result = await detect_search_input(page)
    assert result == "#search-input"

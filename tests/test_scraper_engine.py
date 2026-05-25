"""Tests for the scraper engine module."""

import json
import pytest
from sidecars.hunter.src_py.scraper_engine import extract_json, get_strategy


class TestExtractJson:
    """Unit tests for the extract_json utility."""

    def test_plain_json_object(self):
        result = extract_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_plain_json_array(self):
        result = extract_json('[{"a": 1}]')
        assert result == [{"a": 1}]

    def test_fenced_json(self):
        text = '```json\n{"searchSelector": "#q"}\n```'
        result = extract_json(text)
        assert result == {"searchSelector": "#q"}

    def test_fenced_no_language(self):
        text = '```\n[1, 2, 3]\n```'
        result = extract_json(text)
        assert result == [1, 2, 3]

    def test_json_embedded_in_text(self):
        text = 'Here is the result: {"foo": "bar"} hope that helps.'
        result = extract_json(text)
        assert result == {"foo": "bar"}

    def test_invalid_json_raises(self):
        with pytest.raises(Exception):
            extract_json("this is not json at all")


class TestGetStrategy:
    """Unit tests for the strategy factory."""

    def test_known_strategies(self):
        for name in ("public_api", "static_html", "playwright_public", "generic_search"):
            strategy = get_strategy(name)
            assert strategy is not None

    def test_unknown_strategy_raises(self):
        with pytest.raises(ValueError, match="Unknown scraping strategy"):
            get_strategy("nonexistent")

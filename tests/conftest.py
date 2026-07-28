"""Pytest configuration and shared fixtures for the Sentinel test suite."""

import sys
import os

# Ensure project root is importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

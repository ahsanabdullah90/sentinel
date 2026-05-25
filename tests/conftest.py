"""Pytest configuration and shared fixtures for the Sentinel test suite."""

import sys
import os

# Ensure sidecars are importable
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../proto")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../sidecars/worker/src_py")))

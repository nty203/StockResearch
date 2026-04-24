"""Pytest configuration — adds src to path."""
import sys
import os

# Ensure src package is importable from tests
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

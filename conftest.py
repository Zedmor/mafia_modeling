"""
Pytest configuration file that ensures the project’s source directory (`src/`)
is on Python’s import path during test collection and execution.

Having the package under `src/` keeps the repository root clean, but Python
doesn’t automatically look there when importing.  By inserting the absolute
path to `src` at the *front* of `sys.path`, tests can simply do
`import mafia_transformer ...` without failing.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Absolute path to the project root (directory containing this conftest.py)
ROOT_DIR = Path(__file__).resolve().parent
SRC_DIR = ROOT_DIR / "src"

# Prepend `src/` to sys.path if it is not already present
src_path = str(SRC_DIR)
if src_path not in sys.path:
    sys.path.insert(0, src_path)

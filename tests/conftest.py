"""Test setup.

Without Home Assistant installed, the integration package is registered as a
bare package so the pure-Python modules (protobuf reader, parsers, models,
calc) can be tested without running its HA-dependent ``__init__``. With Home
Assistant installed, the real package is used and the HA tests run too.
"""

from __future__ import annotations

import importlib.util
import pathlib
import sys
import types

ROOT = pathlib.Path(__file__).resolve().parent.parent
HAS_HA = importlib.util.find_spec("homeassistant") is not None

if HAS_HA:
    sys.path.insert(0, str(ROOT))
elif "custom_components.ecoflow_app" not in sys.modules:
    for name, path in (
        ("custom_components", ROOT / "custom_components"),
        ("custom_components.ecoflow_app", ROOT / "custom_components" / "ecoflow_app"),
    ):
        module = types.ModuleType(name)
        module.__path__ = [str(path)]
        sys.modules.setdefault(name, module)

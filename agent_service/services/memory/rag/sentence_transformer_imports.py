"""Serialize first imports from the shared ``sentence_transformers`` package.

Embedding and ReRank load on independent worker threads. Python can deadlock when one
thread imports the package root while another imports ``cross_encoder``. Both loaders
must resolve their exported classes through this single module lock.
"""

from __future__ import annotations

import importlib
import threading
from typing import Any

_IMPORT_LOCK = threading.Lock()


def _load_export(module_name: str, export_name: str) -> Any:
    """Import one sentence-transformers export while excluding sibling first imports."""

    with _IMPORT_LOCK:
        return getattr(importlib.import_module(module_name), export_name)


def load_sentence_transformer_type() -> Any:
    """Return ``SentenceTransformer`` after a serialized package-root import."""

    return _load_export("sentence_transformers", "SentenceTransformer")


def load_cross_encoder_type() -> Any:
    """Return ``CrossEncoder`` after the same serialized import boundary."""

    return _load_export("sentence_transformers.cross_encoder", "CrossEncoder")

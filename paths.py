"""
paths.py
-----------
Centralized path definitions and utilities for the vigilante bot hunter
project. This module computes a single repository root and defines
directories for storing runtime data, hunter data, and evidence. It
also provides helper functions to ensure the directories exist and to
guard against accidentally creating nested ``vigilante`` directories
(e.g., ``vigilante/vigilante``) which can occur when constructing
paths relative to a package named ``vigilante``.

Usage:

.. code-block:: python

    from paths import EVIDENCE_DIR, VIGILANTE_DATA, ensure_dirs, assert_no_nested_vigilante

    ensure_dirs()
    assert_no_nested_vigilante(EVIDENCE_DIR)

    # Use EVIDENCE_DIR when writing evidence bundles
    with open(EVIDENCE_DIR / "example.json", "w") as f:
        f.write("...")

The module honours environment variables ``REFLEXION_ROOT``,
``VIGILANTE_DATA_DIR``, ``HUNTER_DATA_DIR`` and ``EVIDENCE_DIR`` to allow
external configuration of these directories. If unset, sensible
defaults based on the repository layout are used.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable


def _resolve_repo_root() -> Path:
    """Resolve the root of the repository.

    The resolver first checks for an environment override via
    ``REFLEXION_ROOT``. If not set, it climbs up from this module's
    location looking for common sentinels (``.git`` or
    ``Reflexion_ultimate``). If none are found, it falls back to the
    parent of this file.

    Returns:
        Path: The resolved repository root.
    """
    env_root = os.getenv("REFLEXION_ROOT")
    if env_root:
        return Path(env_root).expanduser().resolve()

    here = Path(__file__).resolve()
    for p in [here, *here.parents]:
        if (p / ".git").exists() or (p / "Reflexion_ultimate").exists():
            return p
    # fallback to the parent directory of this file
    return here.parent


# Determine the repository root once
REPO_ROOT: Path = _resolve_repo_root()

# Define the vigilante data directory. This should be distinct from the
# Python package called ``vigilante`` to avoid nested directories. The
# default is ``<REPO_ROOT>/vigilante_data`` but may be overridden via
# ``VIGILANTE_DATA_DIR``.
VIGILANTE_DATA: Path = Path(
    os.getenv("VIGILANTE_DATA_DIR", str(REPO_ROOT / "vigilante_data"))
).expanduser().resolve()

# Define the hunter data directory. This holds evidence and other data
# produced by the military bot hunter. By default it lives under
# ``<REPO_ROOT>/Hunter_data`` but can be overridden via
# ``HUNTER_DATA_DIR``.
HUNTER_DATA: Path = Path(
    os.getenv("HUNTER_DATA_DIR", str(REPO_ROOT / "Hunter_data"))
).expanduser().resolve()

# Define the evidence directory. This is where evidence bundles are
# stored. It defaults to ``<HUNTER_DATA>/evidence``. It may be
# overridden via ``EVIDENCE_DIR``.
EVIDENCE_DIR: Path = Path(
    os.getenv("EVIDENCE_DIR", str(HUNTER_DATA / "evidence"))
).expanduser().resolve()


def ensure_dirs(dirs: Iterable[Path] | None = None) -> None:
    """Ensure that the given directories exist.

    Args:
        dirs: An iterable of directories to create. If None, a sensible
            default set of directories (``VIGILANTE_DATA``,
            ``HUNTER_DATA``, and ``EVIDENCE_DIR``) is used.
    """
    if dirs is None:
        dirs = (VIGILANTE_DATA, HUNTER_DATA, EVIDENCE_DIR)
    for d in dirs:
        d.mkdir(parents=True, exist_ok=True)


def assert_no_nested_vigilante(path: Path) -> None:
    """Guard against nested ``vigilante`` directory names.

    During development it's easy to accidentally construct paths like
    ``.../vigilante/vigilante/...`` when combining a package directory
    named ``vigilante`` with a data directory also called ``vigilante``.
    Such duplication can lead to confusion about where files are
    written. This helper inspects the path and raises an exception if
    nested ``vigilante`` segments are detected.

    Args:
        path: The path to inspect.

    Raises:
        RuntimeError: If the path contains ``.../vigilante/vigilante/...``.
    """
    parts = [p.lower() for p in path.resolve().parts]
    for i in range(len(parts) - 1):
        if parts[i] == "vigilante" and parts[i + 1] == "vigilante":
            raise RuntimeError(
                f"Refusing to use nested vigilante dir: {path}. "
                "Please ensure your data directory has a unique name."
            )


# Create the directories upon import. This helps ensure that modules
# importing from paths.py always have the necessary directories
# available. The assertion helps catch misconfiguration early.
ensure_dirs()
assert_no_nested_vigilante(EVIDENCE_DIR)
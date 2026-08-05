"""Read-only lookup of documented legitimate EIP-7702 delegate projects, sourced from the
existing root-level `fetch_benign_7702_delegates.py`'s SEED_DELEGATES list (imported, not
copied, so there is one source of truth and no risk of drift). Used only to attach neutral
"documented as project X, see this URL" evidence to a packet -- never to imply a safety
verdict, and never derived from the source-analyzer label.
"""
from __future__ import annotations

import importlib.util
import os

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_FETCH_SCRIPT = os.path.join(REPO_ROOT, "fetch_benign_7702_delegates.py")


def _load_seed_delegates() -> list[tuple[str, str, str, str]]:
    if not os.path.exists(_FETCH_SCRIPT):
        return []
    spec = importlib.util.spec_from_file_location("_fetch_benign_7702_delegates_readonly", _FETCH_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)  # module-level code only defines constants/functions (guarded main())
    return list(getattr(module, "SEED_DELEGATES", []))


_SEED_DELEGATES = _load_seed_delegates()
KNOWN_PROJECT_LOOKUP: dict[tuple[str, str], dict] = {
    (chain.lower(), address.lower()): {"project": name, "documentation_url": url}
    for name, url, chain, address in _SEED_DELEGATES
}


def known_project_evidence(chain: str, address: str) -> dict | None:
    key = (str(chain).lower(), str(address).lower())
    return KNOWN_PROJECT_LOOKUP.get(key)

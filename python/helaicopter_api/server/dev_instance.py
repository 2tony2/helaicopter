"""Checkout-local development instance helpers."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha1
from pathlib import Path


API_PORT_BASE = 31000
WEB_PORT_BASE = 32000
PORT_SPAN = 2000


@dataclass(frozen=True, slots=True)
class CheckoutInstance:
    repo_root: Path
    checkout_id: str
    api_port: int
    web_port: int


def build_checkout_instance(repo_root: Path) -> CheckoutInstance:
    normalized = repo_root.resolve()
    digest = sha1(str(normalized).encode("utf-8")).hexdigest()
    offset = int(digest[:8], 16) % PORT_SPAN
    return CheckoutInstance(
        repo_root=normalized,
        checkout_id=digest[:12],
        api_port=API_PORT_BASE + offset,
        web_port=WEB_PORT_BASE + offset,
    )

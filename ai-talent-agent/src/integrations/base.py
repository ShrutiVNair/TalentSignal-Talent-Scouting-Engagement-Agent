from __future__ import annotations

from dataclasses import dataclass


@dataclass
class IntegrationStatus:
    name: str
    enabled: bool
    configured: bool
    mode: str
    detail: str


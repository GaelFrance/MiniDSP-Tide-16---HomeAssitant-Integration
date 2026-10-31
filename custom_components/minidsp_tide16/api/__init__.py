"""Standalone WebSocket client for the miniDSP Tide16.

Importable without Home Assistant - see client.py.
"""

from .client import Tide16Client, Tide16Error
from .discovery import async_scan, candidate_hosts, identify

__all__ = [
    "Tide16Client",
    "Tide16Error",
    "async_scan",
    "candidate_hosts",
    "identify",
]

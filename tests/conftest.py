"""Shared pytest fixtures for the miniDSP Tide16 integration's test suite.

This test suite deliberately does NOT depend on pytest-homeassistant-
custom-component: that package pulls in a full simulated Home Assistant
core (event loop, config dir, recorder, auth, etc.) which is far more
than these tests need, and - at the time this suite was written - only
ships pinned against Home Assistant/Python versions newer than what's
available in the CI/sandbox environment this was authored in (modern
Home Assistant requires Python 3.13+; this environment has 3.10). The
real `homeassistant` core package IS used here (installed from PyPI) for
every module that imports cleanly standalone - config_entries, const,
core, helpers.entity, helpers.entity_platform, helpers.dispatcher,
helpers.event, helpers.aiohttp_client, helpers.config_validation, and
crucially `homeassistant.components.media_player` itself, so
MediaPlayerEntity, MediaPlayerDeviceClass and MediaPlayerEntityFeature
in these tests are the real, unmodified Home Assistant classes/enums,
not hand-rolled stand-ins.

The one thing that does NOT import cleanly standalone (i.e. outside of
Home Assistant's own component loader) is
`homeassistant.components.media_player` itself, because its module-level
code references `homeassistant.components.websocket_api` for one
decorated debug-only websocket command and a browse-media helper -
neither of which this integration's media_player.py uses or exercises.
Home Assistant's own component loader sets these up in a specific order
that avoids the issue; a plain `import` does not. The stub below
provides just enough of `websocket_api`/`http` (as inert no-ops) to let
Python finish importing the real `media_player` module - after which
every class and enum used by these tests is the genuine Home Assistant
implementation.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))


def _install_websocket_api_stub() -> None:
    if "homeassistant.components.websocket_api" in sys.modules:
        return  # already installed by an earlier test session/import

    ws_stub = types.ModuleType("homeassistant.components.websocket_api")

    def _decorator_factory(*_args, **_kwargs):
        def _wrap(fn):
            return fn

        return _wrap

    ws_stub.websocket_command = _decorator_factory
    ws_stub.async_response = lambda fn: fn
    ws_stub.async_register_command = lambda *a, **k: None
    ws_stub.error_message = lambda *a, **k: None
    ws_stub.ERR_NOT_SUPPORTED = "not_supported"
    ws_stub.ERR_UNKNOWN_ERROR = "unknown_error"

    ws_conn_stub = types.ModuleType("homeassistant.components.websocket_api.connection")

    class ActiveConnection:  # pragma: no cover - unused placeholder type
        ...

    ws_conn_stub.ActiveConnection = ActiveConnection
    ws_stub.connection = ws_conn_stub

    sys.modules["homeassistant.components.websocket_api"] = ws_stub
    sys.modules["homeassistant.components.websocket_api.connection"] = ws_conn_stub

    http_stub = types.ModuleType("homeassistant.components.http")
    http_stub.__path__ = []  # mark as a package so a submodule can be registered
    http_stub.KEY_AUTHENTICATED = "ha_authenticated"

    class HomeAssistantView:  # pragma: no cover - unused placeholder type
        ...

    http_stub.HomeAssistantView = HomeAssistantView
    sys.modules["homeassistant.components.http"] = http_stub

    http_auth_stub = types.ModuleType("homeassistant.components.http.auth")
    http_auth_stub.async_sign_path = lambda *a, **k: ""
    sys.modules["homeassistant.components.http.auth"] = http_auth_stub


_install_websocket_api_stub()

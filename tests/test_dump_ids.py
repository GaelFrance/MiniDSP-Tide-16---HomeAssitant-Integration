import os
from pathlib import Path

import pytest
from homeassistant.helpers import entity_registry as er

from .test_merged import _connect, _setup


@pytest.mark.skipif(not os.environ.get("DUMP_IDS"), reason="manual")
async def test_dump(hass, entry, fake_client):
    await _setup(hass, entry)
    await _connect(hass, fake_client.instances[-1])
    reg = er.async_get(hass)
    ids = sorted(e.entity_id for e in reg.entities.values())
    disabled = sorted(e.entity_id for e in reg.entities.values() if e.disabled_by)
    out = Path(os.environ["DUMP_IDS"])
    await hass.async_add_executor_job(out.write_text, "\n".join(ids) + "\n")
    await hass.async_add_executor_job(
        Path(f"{out}.disabled").write_text, "\n".join(disabled) + "\n"
    )

#!/usr/bin/env python3
"""Regenerate the card's baked-in layout from the annotated record.

`docs/panel-layout.annotated.yaml` is the source: it carries every element box
on the plate together with the reasoning for the number. The card ships that
same geometry as the `PANEL_LAYOUT` constant, which is what this writes.

Edit the annotated file, run this, then run `tools/check_layout_sync.py`.
Never hand-edit PANEL_LAYOUT - the annotated file is where the "why" lives,
and an edit that skips it loses the only record of how a number was derived.

The `card_mod` block is dropped on the way through: the card sets its own
container and strips ha-card's chrome itself, so card-mod is not a dependency
any more.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
ANNOTATED = ROOT / "docs" / "panel-layout.annotated.yaml"
MODULE = ROOT / "custom_components" / "minidsp_tide16" / "frontend" / "tide16-panel.js"
NEEDLE = "const PANEL_LAYOUT = "
STAMP = "v<version>"


def main() -> int:
    view = yaml.safe_load(ANNOTATED.read_text(encoding="utf-8"))
    card = view[0]["cards"][0]["cards"][0]
    if card["type"] != "picture-elements":
        raise SystemExit(f"{ANNOTATED}: expected a picture-elements card")
    layout = {k: v for k, v in card.items() if k != "card_mod"}

    # The plate stamp is not a number to bake in: since v2.5.7 the card reads
    # its version off the module URL, and a literal here would drift again.
    for el in layout["elements"]:
        if re.fullmatch(r"v\d+\.\d+\.\d+", str(el.get("title", ""))):
            el["title"] = STAMP

    body = json.dumps(layout, indent=2, ensure_ascii=False)
    body = body.replace(json.dumps(STAMP), "`v${TIDE16_VERSION}`")
    # Everything after the opening line is one level in, so the constant reads
    # like hand-written source rather than a pasted blob.
    body = "\n".join(("  " + ln if i else ln) for i, ln in enumerate(body.split("\n")))

    src = MODULE.read_text(encoding="utf-8")
    start = src.index(NEEDLE) + len(NEEDLE)
    depth = 0
    end = None
    for i, ch in enumerate(src[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    if end is None:
        raise SystemExit(f"{MODULE}: PANEL_LAYOUT is not balanced")

    updated = src[:start] + body + src[end:]
    if updated == src:
        print(f"layout already current - {len(layout['elements'])} elements")
        return 0
    MODULE.write_text(updated, encoding="utf-8")
    print(f"wrote PANEL_LAYOUT - {len(layout['elements'])} elements")
    return 0


if __name__ == "__main__":
    sys.exit(main())

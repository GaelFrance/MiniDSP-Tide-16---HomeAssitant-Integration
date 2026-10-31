#!/usr/bin/env python3
"""Prove the card's baked-in layout still matches the annotated record.

`docs/panel-layout.annotated.yaml` is where every element box on the plate is
explained - what it was anchored to on the artwork and why it is that number.
The card in `custom_components/minidsp_tide16/frontend/tide16-panel.js` carries the
same boxes as data, and that copy is the one that ships.

Two copies of the same geometry is exactly the drift that has bitten this
repo before, so this is the check: the annotated file, minus the `card_mod`
block the card no longer needs, must equal `PANEL_LAYOUT` exactly.

Run it before every release:  python3 tools/check_layout_sync.py
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


def from_yaml() -> dict:
    view = yaml.safe_load(ANNOTATED.read_text(encoding="utf-8"))
    card = view[0]["cards"][0]["cards"][0]
    if card["type"] != "picture-elements":
        raise SystemExit(f"{ANNOTATED}: expected a picture-elements card")
    # The record's `title: v...` is the stamp as last drawn; the card fills in
    # the running version, so only the placeholder is compared.
    for el in card["elements"]:
        if re.fullmatch(r"v\d+\.\d+\.\d+", str(el.get("title", ""))):
            el["title"] = STAMP
    return {k: v for k, v in card.items() if k != "card_mod"}


def from_module() -> dict:
    src = MODULE.read_text(encoding="utf-8")
    start = src.index(NEEDLE) + len(NEEDLE)
    # The literal is emitted as JSON, so brace matching is enough - there are
    # no braces inside strings to confuse it.
    depth = 0
    for end, ch in enumerate(src[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                # The plate stamp is the one non-JSON value: it reads the
                # version off the module URL at run time (v2.5.7).
                body = src[start : end + 1].replace("`v${TIDE16_VERSION}`", json.dumps(STAMP))
                return json.loads(body)
    raise SystemExit(f"{MODULE}: PANEL_LAYOUT is not balanced")


def main() -> int:
    want, got = from_yaml(), from_module()
    if want == got:
        print(f"layout in sync - {len(got['elements'])} elements")
        return 0

    print("LAYOUT DRIFT between the annotated record and the shipped card\n")
    w, g = want.get("elements", []), got.get("elements", [])
    if len(w) != len(g):
        print(f"  element count: annotated {len(w)}, card {len(g)}")
    for i, (a, b) in enumerate(zip(w, g)):
        if a != b:
            print(f"  element {i} ({a.get('type')}) differs:")
            for key in sorted(set(a) | set(b)):
                if a.get(key) != b.get(key):
                    print(f"    {key}: annotated {a.get(key)!r} card {b.get(key)!r}")
    for key in sorted(set(want) | set(got)):
        if key != "elements" and want.get(key) != got.get(key):
            print(f"  {key}: annotated {want.get(key)!r} card {got.get(key)!r}")
    return 1


if __name__ == "__main__":
    sys.exit(main())

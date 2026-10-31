"""Talk to a Tide16 from a terminal, with no Home Assistant involved.

    cd custom_components/minidsp_tide16
    python3 -m api 192.168.1.212           # dump state
    python3 -m api 192.168.1.212 --watch   # follow pushes
    python3 -m api --scan                  # find units on this subnet
    python3 -m api --scan 10.0.0.0/24      # ...or on another one

This exists to keep the protocol honest: if the integration and this disagree,
the bug is above the API layer.
"""

from __future__ import annotations

import asyncio
import json
import socket
import sys

from .client import Tide16Client, Tide16Error
from .const import GET_RMS_DB, REFRESH_ENDPOINTS
from .discovery import async_scan, candidate_hosts


async def scan(cidr: str | None) -> int:
    """Sweep a subnet and print what answers as a Tide16."""
    if cidr is None:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.connect(("8.8.8.8", 80))
        mine = probe.getsockname()[0]
        probe.close()
        cidr = f"{mine}/24"
        print(f"this machine is {mine}, sweeping {cidr}", file=sys.stderr)

    hosts = candidate_hosts(cidr)
    if not hosts:
        print(f"{cidr} is too big to sweep - narrow it to a /24", file=sys.stderr)
        return 2

    found = await async_scan(hosts)
    if not found:
        print("no Tide16 found. A unit in standby is off the network entirely -"
              " switch it on and try again.")
        return 1
    for unit in found:
        print(f"{unit['host']}:{unit['port']}  firmware {unit['version']}"
              f"  preset {unit['preset']}")
    return 0


async def main(host: str, watch: bool) -> int:
    pushes: list[str] = []
    client = Tide16Client(
        host,
        on_notification=lambda name, payload: pushes.append(
            f"{name}: {json.dumps(payload)[:120]}"
        ),
    )
    await client.start()

    for _ in range(50):  # ~5s for the supervisor to land a connection
        if client.connected:
            break
        await asyncio.sleep(0.1)
    if not client.connected:
        print(f"no connection to {client.url}", file=sys.stderr)
        await client.stop()
        return 1

    try:
        for endpoint in (*REFRESH_ENDPOINTS, GET_RMS_DB):
            try:
                data = await client.request(endpoint)
            except Tide16Error as err:
                print(f"{endpoint:<28} !! {err}")
                continue
            rendered = json.dumps(data)
            if len(rendered) > 150:
                rendered = rendered[:147] + "..."
            print(f"{endpoint:<28} {rendered}")

        if watch:
            print("\nwatching for pushes, ctrl-c to stop\n", file=sys.stderr)
            seen = 0
            while True:
                await asyncio.sleep(0.5)
                while seen < len(pushes):
                    print("  push  " + pushes[seen])
                    seen += 1
    finally:
        await client.stop()
    return 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if "--scan" in sys.argv:
        try:
            raise SystemExit(asyncio.run(scan(args[0] if args else None)))
        except KeyboardInterrupt:
            raise SystemExit(0)
    if not args:
        print(__doc__, file=sys.stderr)
        raise SystemExit(2)
    try:
        raise SystemExit(asyncio.run(main(args[0], "--watch" in sys.argv)))
    except KeyboardInterrupt:
        raise SystemExit(0)

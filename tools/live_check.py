"""Read live hood state using the production client. Credentials stay in memory."""

import argparse
import asyncio
import getpass
import json
import os
import sys
from pathlib import Path

import aiohttp

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from custom_components.pando_hood.client import PandoError
from custom_components.pando_hood.cloud import Cloud

# Public leaf certificate verified on 2026-10-12: trusted chain + correct hostname,
# but expired. Never discover a replacement pin automatically.
VERIFIED_PIN = "a73d5cf93adafc420f0d076b31564953a1d0d4433359f9e2e1a70828206ab2fc"
REPORT = Path("/private/tmp/pando-app-private/cloud-live-check.json")


async def light_check(hood, cloud, settle_time=2):
    key = "device.lightOnOff"
    initial = (await cloud.refresh(hood.uid)).get(key)
    if initial not in (0, 1):
        raise PandoError("No valid initial light state; no command sent")
    target = 1 - initial
    try:
        await hood.set_values(cloud, {key: target})
        observed = await cloud.refresh(hood.uid)
        if observed.get(key) != target:
            raise PandoError("Light command was acknowledged but expected state was not reported")
        await asyncio.sleep(settle_time)
    finally:
        try:
            await hood.set_values(cloud, {key: initial})
            restored = await cloud.refresh(hood.uid)
            if restored.get(key) != initial:
                raise PandoError("Light restoration was not confirmed; check it in Pando")
        except PandoError as error:
            raise PandoError(
                "Could not confirm light restoration; check the light in Pando now"
            ) from error
    return True


async def main(test_light=False):
    email = input("Pando account email: ").strip()
    password = getpass.getpass("Pando password (hidden): ")
    print("The MQTT certificate is expired. Normal verification will reject it.")
    print("Its chain and hostname were independently verified on 2026-10-12.")
    print("Optional exact SHA-256 pin: " + VERIFIED_PIN)
    choice = input("Type PIN to trust only this certificate, or Enter for normal verification: ")
    fingerprint = VERIFIED_PIN if choice == "PIN" else ""
    async with aiohttp.ClientSession() as session:
        cloud = Cloud(session, email, password, fingerprint)
        try:
            hoods = await cloud.devices()
            if not hoods:
                raise PandoError("No enabled hoods found")
            if len(hoods) == 1:
                hood = hoods[0]
            else:
                for i, h in enumerate(hoods):
                    print(f"{i + 1}: {h.name}")
                hood = hoods[int(input("Hood number: ")) - 1]
            await cloud.start([hood], lambda uid: None, lambda: None)
            state = await cloud.refresh(hood.uid)
            report = {
                "success": True,
                "certificate_pinning_enabled": bool(fingerprint),
                "state": state,
            }
            if test_light:
                print("Testing the light briefly, then restoring its original on/off state.")
                report["light_test_restored"] = await light_check(hood, cloud)
                report["state"] = await cloud.refresh(hood.uid)
                print("Light command and restoration both confirmed by reported state.")
            REPORT.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            fd = os.open(REPORT, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            os.fchmod(fd, 0o600)
            with os.fdopen(fd, "w") as output:
                json.dump(report, output, indent=2)
            print(
                "Live state received. Credentials were not saved."
                if test_light
                else "Live state received. No controls were changed; credentials were not saved."
            )
            print("Private result: " + str(REPORT))
        finally:
            await cloud.close()


if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument(
            "--test-light",
            action="store_true",
            help="Briefly toggle the light and restore it; keep other controls idle",
        )
        args = parser.parse_args()
        asyncio.run(main(args.test_light))
    except PandoError as error:
        print(f"Check failed: {error}")
    except (KeyboardInterrupt, EOFError):
        print("Cancelled.")

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


# ---------------------------------------------------------------------------
# Fake GitHub API payloads
# ---------------------------------------------------------------------------

STABLE_RELEASE: dict = {
    "name": "v3.7.0",
    "tag_name": "v3.7.0",
    "assets": [
        {
            "name": "EMS-ESP-3_7_0-ESP32-16MB+.bin",
            "browser_download_url": "https://example.com/EMS-ESP-3_7_0-ESP32-16MB+.bin",
        },
        {
            "name": "EMS-ESP-3_7_0-ESP32S3-16MB+.bin",
            "browser_download_url": "https://example.com/EMS-ESP-3_7_0-ESP32S3-16MB+.bin",
        },
    ],
}

DEV_RELEASE: dict = {
    "name": "Development Build v3.8.0-dev",
    "tag_name": "latest",
    "assets": [
        {
            "name": "EMS-ESP-3_8_0-dev-ESP32-16MB+.bin",
            "browser_download_url": "https://example.com/EMS-ESP-3_8_0-dev-ESP32-16MB+.bin",
        },
        {
            "name": "EMS-ESP-3_8_0-dev-ESP32S3-16MB+.bin",
            "browser_download_url": "https://example.com/EMS-ESP-3_8_0-dev-ESP32S3-16MB+.bin",
        },
    ],
}

# Realistic esptool v5 flash-id output
PROBE_OUTPUT_V5 = (
    "esptool v5.0.0\n"
    "Connected to ESP32 on /dev/ttyUSB0:\n"
    "Chip type: ESP32\n"
    "MAC:                aa:bb:cc:dd:ee:ff\n"
)

PROBE_OUTPUT_V4 = (
    "esptool.py v4.9.0\n"
    "Serial port /dev/ttyUSB0\n"
    "Connecting...\n"
    "Chip is ESP32-D0WD-V3\n"
    "MAC: aa:bb:cc:dd:ee:ff\n"
)

# Fake serial output from EMS-ESP after boot
SERIAL_VERIFY_LINES = [
    b" Version: 3.7.0\n",
    b" Board profile: esp32\n",
    b" Model: EMS-ESP32\n",
    b"",  # triggers next time.time() check → loop exits
]


def make_requests_mock(release_data: dict) -> MagicMock:
    """Return a requests.get mock that serves metadata and binary downloads."""

    def _get(url: str, **kwargs: object) -> MagicMock:
        response = MagicMock()
        response.raise_for_status.return_value = None
        if kwargs.get("stream"):
            # Firmware binary download
            response.iter_content.return_value = iter([b"fake_firmware_content"])
        else:
            # Release metadata
            response.json.return_value = release_data
        return response

    mock = MagicMock(side_effect=_get)
    return mock


def make_subprocess_mock(
    probe_output: str = PROBE_OUTPUT_V5,
    flash_returncode: int = 0,
) -> MagicMock:
    """Return a subprocess.run mock for esptool probe and write_flash calls."""

    def _run(cmd: list, **kwargs: object) -> MagicMock:
        result = MagicMock()
        if kwargs.get("capture_output"):
            # probe_device call
            result.returncode = 0
            result.stdout = probe_output
            result.stderr = ""
        else:
            # write_flash call
            result.returncode = flash_returncode
        return result

    return MagicMock(side_effect=_run)

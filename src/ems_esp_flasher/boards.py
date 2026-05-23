from __future__ import annotations

from dataclasses import dataclass
from importlib.resources import files
from pathlib import Path


@dataclass(frozen=True)
class BoardConfig:
    """Configuration for a supported EMS-ESP board variant."""

    name: str                # User-facing CLI name: "esp32" or "esp32s3"
    chip: str                # esptool --chip argument
    mcu: str                 # Segment used in firmware filenames, e.g. "ESP32-16MB+"
    flash_freq: str          # Flash frequency: "40m" or "80m"
    flash_size: str          # Flash size: "16MB"
    bootloader_address: str  # Memory address for the bootloader binary

    def data_dir(self) -> Path:
        """Return the path to bundled board-specific binaries.

        bootloader.bin, partitions.bin, and boot_app0.bin are bundled as
        package data rather than fetched from GitHub at runtime. These files
        are tied to the hardware profile (not the firmware version) and are
        stable across firmware updates. Bundling them keeps 'flash' fully
        self-contained after install — no network access is required for
        the board support files.
        """
        resource = files("ems_esp_flasher").joinpath(f"data/{self.name}")
        return Path(str(resource))


BOARDS: dict[str, BoardConfig] = {
    "esp32": BoardConfig(
        name="esp32",
        chip="esp32",
        mcu="ESP32-16MB+",
        flash_freq="40m",
        flash_size="16MB",
        bootloader_address="0x1000",
    ),
    "esp32s3": BoardConfig(
        name="esp32s3",
        chip="esp32s3",
        mcu="ESP32S3-16MB+",
        flash_freq="80m",
        flash_size="16MB",
        bootloader_address="0x0000",
    ),
}

BOARD_NAMES = list(BOARDS.keys())

from __future__ import annotations

import re
import subprocess
import sys
import time
from pathlib import Path

import serial

from .boards import BoardConfig


def _flash_id_subcmd() -> str:
    """Return the correct flash-id subcommand name for the installed esptool version.

    esptool v5 renamed 'flash_id' to 'flash-id' (underscore → hyphen).
    We detect the version at runtime so the tool works with both v4 and v5.
    """
    try:
        from importlib.metadata import version as pkg_version

        major = int(pkg_version("esptool").split(".")[0])
        return "flash-id" if major >= 5 else "flash_id"
    except Exception:
        return "flash_id"  # safe fallback


def probe_device(port: str | None) -> tuple[str, str]:
    """Use esptool to probe the connected ESP32.

    Returns (detected_port, mac_address). Raises RuntimeError on failure.
    """
    cmd = [sys.executable, "-m", "esptool"]
    if port:
        cmd += ["--port", port]
    cmd.append(_flash_id_subcmd())

    result = subprocess.run(cmd, capture_output=True, text=True)
    output = result.stdout + result.stderr

    if result.returncode != 0:
        raise RuntimeError(f"Failed to connect to ESP32:\n{output.strip()}")

    mac = _parse_mac(output)
    detected_port = _parse_port(output, port)
    return detected_port, mac


def _parse_mac(output: str) -> str:
    match = re.search(r"MAC[:\s]+([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})", output)
    if not match:
        raise RuntimeError("Could not parse MAC address from esptool output")
    return match.group(1).lower()


def _parse_port(output: str, requested_port: str | None) -> str:
    # esptool v5 format: "Connected to ESP32 on /dev/ttyXXX:"
    match = re.search(r"Connected to .+ on ([^\s:]+)[:\s]", output)
    if match:
        return match.group(1)
    # esptool v4 format: "Serial port /dev/ttyXXX"
    match = re.search(r"Serial port ([^\s]+)", output)
    if match:
        return match.group(1)
    if requested_port:
        return requested_port
    raise RuntimeError("Could not detect serial port from esptool output")


def write_flash(board: BoardConfig, port: str, firmware_file: Path) -> None:
    """Invoke esptool write_flash as a subprocess with inherited stdout.

    Stdout is inherited (not captured) so the user sees real-time flash progress.
    """
    data = board.data_dir()
    cmd = [
        sys.executable, "-m", "esptool",
        "--port", port,
        "--chip", board.chip,
        "--baud", "921600",
        "--before", "default_reset",
        "--after", "hard_reset",
        "write_flash",
        "-z",
        "--flash_mode", "dio",
        "--flash_freq", board.flash_freq,
        "--flash_size", board.flash_size,
        board.bootloader_address, str(data / "bootloader.bin"),
        "0x8000",                  str(data / "partitions.bin"),
        "0xe000",                  str(data / "boot_app0.bin"),
        "0x10000",                 str(firmware_file),
    ]

    result = subprocess.run(cmd)
    if result.returncode != 0:
        raise RuntimeError("esptool write_flash failed")


def verify_flash(port: str, timeout: float = 6.0) -> dict[str, str]:
    """Connect via serial after flashing to verify the EMS-ESP booted correctly.

    Sends 'show system' and collects lines containing version/board info.
    Replaces the minicom-based check from the original bash script. Using
    pyserial directly is cross-platform and avoids an external binary dependency
    (minicom is Linux-only and not pip-installable).

    Returns a dict of {field: value} pairs, e.g. {"Version": "3.7.0", ...}.
    An empty dict means verification produced no output — not a fatal error.
    """
    time.sleep(3)  # Wait for ESP32 to reboot after hard_reset

    results: dict[str, str] = {}
    try:
        with serial.Serial(port, baudrate=115200, timeout=1) as ser:
            ser.write(b"show system\n")
            deadline = time.time() + timeout
            while time.time() < deadline:
                line = ser.readline().decode("utf-8", errors="replace").strip()
                for key in ("Version:", "Board profile:", "Model:"):
                    if key in line:
                        value = line.split(key, 1)[-1].strip()
                        results[key.rstrip(":")] = value
    except serial.SerialException:
        pass  # Some platforms don't allow serial reads immediately after a flash

    return results

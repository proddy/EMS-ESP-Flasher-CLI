from __future__ import annotations

import shutil
from pathlib import Path
from typing import Annotated, NoReturn, Optional

import typer

from .boards import BOARD_NAMES, BOARDS
from .flash import probe_device, verify_flash, write_flash
from .github import download_firmware, get_firmware_path, get_release, get_version_string

DEFAULT_FIRMWARE_DIR = Path.home() / ".local" / "share" / "ems-esp" / "firmware"

app = typer.Typer(
    name="ems-esp-flasher",
    help="EMS-ESP firmware flash tool. Flashes ESP32-based EMS-ESP devices.",
    no_args_is_help=True,
)

firmware_app = typer.Typer(
    help="Manage locally cached EMS-ESP firmware.",
    no_args_is_help=True,
)
app.add_typer(firmware_app, name="firmware")


def _die(message: str) -> NoReturn:
    typer.echo(f"Error: {message}", err=True)
    raise typer.Exit(code=1)


@firmware_app.command("fetch")
def firmware_fetch(
    board: Annotated[
        Optional[str],
        typer.Option(help=f"Limit download to one board. Choices: {', '.join(BOARD_NAMES)}"),
    ] = None,
    version: Annotated[
        Optional[str],
        typer.Option(help="Firmware version to fetch, e.g. '3.7.0'. Defaults to latest stable."),
    ] = None,
    dev: Annotated[
        bool,
        typer.Option("--dev", help="Fetch the latest development/pre-release build."),
    ] = False,
    firmware_dir: Annotated[
        Path,
        typer.Option(help="Local firmware cache directory."),
    ] = DEFAULT_FIRMWARE_DIR,
    force: Annotated[
        bool,
        typer.Option("--force", help="Re-download even if the file is already cached."),
    ] = False,
) -> None:
    """Download EMS-ESP firmware binaries to the local cache."""
    if dev and version:
        _die("--dev and --version are mutually exclusive.")
    if board and board not in BOARDS:
        _die(f"Unknown board '{board}'. Choices: {', '.join(BOARD_NAMES)}")

    boards_to_fetch = [BOARDS[board]] if board else list(BOARDS.values())

    try:
        typer.echo("Fetching release info from GitHub...")
        release = get_release(version, dev)
    except Exception as exc:
        _die(f"Could not fetch release info: {exc}")

    typer.echo(f"Release: {release['name']}")

    for b in boards_to_fetch:
        dest = get_firmware_path(release, b.mcu, firmware_dir)
        if dest.exists() and not force:
            typer.echo(f"  {b.name}: already cached ({dest.name})")
            continue
        typer.echo(f"  {b.name}: downloading {dest.name}...", nl=False)
        try:
            download_firmware(release, b.mcu, firmware_dir, force=True)
        except Exception as exc:
            typer.echo("")  # newline after the nl=False above
            _die(f"Download failed for {b.name}: {exc}")
        typer.echo(" done")

    typer.echo("Firmware fetch complete.")


@firmware_app.command("clean")
def firmware_clean(
    firmware_dir: Annotated[
        Path,
        typer.Option(help="Local firmware cache directory to delete."),
    ] = DEFAULT_FIRMWARE_DIR,
) -> None:
    """Delete all locally cached firmware files."""
    if not firmware_dir.exists():
        typer.echo(f"Cache directory does not exist: {firmware_dir}")
        return

    typer.confirm(f"Delete all cached firmware at {firmware_dir}?", abort=True)
    shutil.rmtree(firmware_dir)
    typer.echo(f"Deleted firmware cache: {firmware_dir}")


@app.command()
def flash(
    board: Annotated[
        str,
        typer.Argument(help=f"Target board. Choices: {', '.join(BOARD_NAMES)}"),
    ],
    port: Annotated[
        str,
        typer.Argument(help="Serial port (e.g. /dev/ttyUSB0) or 'auto' for autodetect."),
    ],
    version: Annotated[
        Optional[str],
        typer.Option(help="Firmware version to flash, e.g. '3.7.0'. Defaults to latest stable."),
    ] = None,
    dev: Annotated[
        bool,
        typer.Option("--dev", help="Flash the latest development/pre-release build."),
    ] = False,
    firmware_dir: Annotated[
        Path,
        typer.Option(help="Local firmware cache directory."),
    ] = DEFAULT_FIRMWARE_DIR,
    yes: Annotated[
        bool,
        typer.Option("--yes", "-y", help="Skip the confirmation prompt (for scripted use)."),
    ] = False,
) -> None:
    """Flash EMS-ESP firmware to a connected ESP32 board."""
    if dev and version:
        _die("--dev and --version are mutually exclusive.")
    if board not in BOARDS:
        _die(f"Unknown board '{board}'. Choices: {', '.join(BOARD_NAMES)}")

    board_config = BOARDS[board]

    try:
        typer.echo("Fetching release info from GitHub...")
        release = get_release(version, dev)
    except Exception as exc:
        _die(f"Could not fetch release info: {exc}")

    version_str = get_version_string(release, dev)

    # Resolve firmware file; auto-fetch if not in local cache
    firmware_file = get_firmware_path(release, board_config.mcu, firmware_dir)
    if not firmware_file.exists():
        typer.echo("Firmware not found in local cache — fetching from GitHub...")
        try:
            firmware_file = download_firmware(
                release, board_config.mcu, firmware_dir, force=False
            )
        except Exception as exc:
            _die(f"Failed to download firmware: {exc}")

    # Probe the device
    typer.echo("Probing connected ESP32...")
    probe_port = port if port != "auto" else None
    try:
        detected_port, mac = probe_device(probe_port)
    except RuntimeError as exc:
        _die(str(exc))

    # Confirmation summary
    typer.echo("")
    typer.echo("Flash configuration:")
    typer.echo(f"  Board:            {board}")
    typer.echo(f"  Chip:             {board_config.chip}")
    typer.echo(f"  Port:             {detected_port}")
    typer.echo(f"  MAC address:      {mac}")
    typer.echo(f"  Firmware version: {version_str}")
    typer.echo(f"  Firmware file:    {firmware_file.name}")
    typer.echo(f"  MCU:              {board_config.mcu}")
    typer.echo("")

    if not yes:
        typer.confirm("Continue?", abort=True)

    typer.echo("Flashing firmware (this may take a minute)...")
    try:
        write_flash(board_config, detected_port, firmware_file)
    except RuntimeError as exc:
        _die(str(exc))

    typer.echo("Connecting to EMS-ESP for post-flash verification...")
    info = verify_flash(detected_port)

    typer.echo("")
    if info:
        for key, value in info.items():
            typer.echo(f"  {key}: {value}")
        typer.echo("")
        typer.secho(
            f"EMS-ESP successfully flashed to v{version_str}.",
            fg=typer.colors.GREEN,
        )
    else:
        typer.secho(
            f"EMS-ESP flashed to v{version_str}. "
            "(Could not read back device info — verify manually via the WebUI.)",
            fg=typer.colors.YELLOW,
        )

    typer.echo("")

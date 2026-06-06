from __future__ import annotations

import os
from pathlib import Path

import requests

_GITHUB_API = "https://api.github.com"
_REPO = "emsesp/EMS-ESP32"
_TIMEOUT_META = 30
_TIMEOUT_DOWNLOAD = 300  # firmware files can be large


def _headers() -> dict[str, str]:
    """Build request headers, including an optional GitHub token.

    A GITHUB_TOKEN env var is used as a Bearer token when present.
    Without it, GitHub's unauthenticated rate limit (60 req/hr per IP) applies,
    which is sufficient for normal use but may be exceeded in CI or on shared IPs.
    """
    token = os.environ.get("GITHUB_TOKEN")
    if token:
        return {"Authorization": f"Bearer {token}"}
    return {}


def get_release(version: str | None, dev: bool) -> dict:
    """Fetch release metadata from the GitHub API.

    - dev=True        → the rolling pre-release tagged "latest"
    - version="3.7.0" → specific stable release (leading 'v' is optional)
    - default         → latest stable release
    """
    if dev:
        url = f"{_GITHUB_API}/repos/{_REPO}/releases/tags/latest"
    elif version:
        tag = version if version.startswith("v") else f"v{version}"
        url = f"{_GITHUB_API}/repos/{_REPO}/releases/tags/{tag}"
    else:
        url = f"{_GITHUB_API}/repos/{_REPO}/releases/latest"

    resp = requests.get(url, headers=_headers(), timeout=_TIMEOUT_META)
    resp.raise_for_status()
    return resp.json()


def get_version_string(release: dict, dev: bool) -> str:
    """Extract a clean version string from release metadata."""
    name: str = release["name"]
    if dev:
        # Dev releases: "Development Build v3.7.0-dev+something"
        return name.removeprefix("Development Build v").strip()
    else:
        # Stable releases: "v3.7.0"
        return name.lstrip("v").strip()


def get_firmware_path(release: dict, mcu: str, firmware_dir: Path) -> Path:
    """Return the expected local path for a firmware asset (file may not exist yet)."""
    for asset in release["assets"]:
        if asset["name"].endswith(f"{mcu}.bin"):
            return firmware_dir / asset["name"]
    raise RuntimeError(
        f"No firmware asset found for MCU '{mcu}' in release '{release['name']}'"
    )


def download_firmware(release: dict, mcu: str, firmware_dir: Path, force: bool) -> Path:
    """Download the firmware binary for a specific MCU to the local cache.

    Skips the download if the file already exists and force=False.
    Returns the local path to the firmware file.
    """
    dest = get_firmware_path(release, mcu, firmware_dir)

    if dest.exists() and not force:
        return dest

    firmware_dir.mkdir(parents=True, exist_ok=True)

    asset_url: str | None = None
    for asset in release["assets"]:
        if asset["name"] == dest.name:
            asset_url = asset["browser_download_url"]
            break

    if not asset_url:
        raise RuntimeError(
            f"No download URL found for '{dest.name}' in release '{release['name']}'"
        )

    resp = requests.get(
        asset_url, headers=_headers(), stream=True, timeout=_TIMEOUT_DOWNLOAD
    )
    resp.raise_for_status()

    with dest.open("wb") as f:
        for chunk in resp.iter_content(chunk_size=65536):
            f.write(chunk)

    return dest

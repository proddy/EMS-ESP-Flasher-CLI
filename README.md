# EMS-ESP flash tool - Command Line Interface

A cross-platform CLI tool to flash
[EMS-ESP](https://github.com/emsesp/EMS-ESP32) firmware to ESP32-based EMS-ESP
devices.

## Installation

### 1. Install `uv`

[uv](https://docs.astral.sh/uv/) is a fast Python package manager.
Follow the official install instructions to get `uv` on your system.

### 2. Install `ems-esp-flasher`

```sh
uv tool install git+https://github.com/emsesp/EMS-ESP-Flasher-CLI
```

This makes the `ems-esp-flasher` command available system-wide.
No virtual environment management or `pip` required.

To upgrade to the latest version:

```sh
uv tool upgrade ems-esp-flasher-cli
```

### WSL2 / Windows note

To access a Windows COM port from WSL2, install `usbipd-win`:

```sh
winget install usbipd
```

Then from a PowerShell admin window: `usbipd bind --busid <id>` followed by 
`usbipd attach -a -w -b <id>`.
The port will appear as `/dev/ttyUSB0` or `/dev/ttyACM0` in the WSL2 environment.

## Usage

### Flash a board (simplest — fetches firmware automatically)

```sh
ems-esp-flasher flash esp32 auto
ems-esp-flasher flash esp32s3 /dev/ttyUSB0
```

`esp32` targets the E32 V2 Gateway; `esp32s3` targets the S3 board.
Use `auto` to let the tool detect the serial port, or supply a path like `/dev/ttyUSB0`.

### Flash a specific version

```sh
ems-esp-flasher flash esp32 auto --version 3.7.0
```

### Flash the latest development build

```sh
ems-esp-flasher flash esp32s3 auto --dev
```

### Pre-fetch firmware (optional — useful on slow connections)

```sh
# Fetch all boards, latest stable
ems-esp-flasher firmware fetch

# Fetch only esp32, specific version
ems-esp-flasher firmware fetch --board esp32 --version 3.7.0

# Force re-download
ems-esp-flasher firmware fetch --force
```

### Delete cached firmware

```sh
ems-esp-flasher firmware clean
```

### Skip the confirmation prompt (for scripts/CI)

```sh
ems-esp-flasher flash esp32 auto --yes
```

### Full help

```sh
ems-esp-flasher --help
ems-esp-flasher flash --help
ems-esp-flasher firmware --help
```

## GitHub API rate limits

By default the tool uses the GitHub API anonymously (60 requests/hour per IP).
For CI or shared environments, set a `GITHUB_TOKEN` environment variable to
authenticate and avoid rate limits:

```sh
export GITHUB_TOKEN=ghp_...
ems-esp-flasher flash esp32 auto
```

## Testing

The test suite uses [pytest](https://pytest.org/) and runs entirely without a physical
device — all serial communication, esptool subprocess calls, and GitHub HTTP requests
are mocked.

### 1. Clone the repository and install dev dependencies

```sh
git clone https://github.com/emsesp/EMS-ESP-Flasher-CLI
cd EMS-ESP-Flasher-CLI
uv sync
```

`uv sync` installs both the package and its dev dependencies (including pytest) into
an isolated virtual environment.

### 2. Run the tests

```sh
uv run pytest
```

For verbose output showing each test name:

```sh
uv run pytest -v
```

To run only a specific test file or test class:

```sh
uv run pytest tests/test_flash.py -v
uv run pytest tests/test_firmware.py::TestFirmwareFetch -v
```

### Test structure

| File | What it covers |
|---|---|
| `tests/test_firmware.py` | `firmware fetch` and `firmware clean` subcommands |
| `tests/test_flash.py` | `flash` command — happy path, error handling, serial verification |
| `tests/conftest.py` | Shared fixtures and mock factories |

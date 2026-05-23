## Troubleshooting

### "Failed to connect to ESP32"

The device could not be detected on the serial port.

- **Check the USB cable** — some cables are power-only and do not carry data.
- **Check the port** — run `ls /dev/tty*` before and after plugging in the
device to identify the correct port, then pass it explicitly instead of `auto`.
- **Driver missing** — the E32 V2 uses a CH340/CH341 USB-serial chip. On Linux
it is usually supported out of the box.
- **Permission denied** — on Linux your user may not be in the `dialout` group.
Add yourself with `sudo usermod -aG dialout $USER` and log out/in (requires root
and a new login session).
- **WSL2** — COM ports are not exposed to WSL2 by default. See the 
[WSL2 note](#wsl2--windows-note) in the Installation section.

### "No firmware asset found for MCU '...'"

The requested firmware version does not include a binary for that board.

- Verify the version exists on the 
[EMS-ESP32 releases page](https://github.com/emsesp/EMS-ESP32/releases).
- Check the exact version string — omit the leading `v` (e.g. `--version 3.7.0` not 
`--version v3.7.0`).

### "Could not fetch release info" / HTTP 403

The GitHub API rate limit has been exceeded (60 requests/hour for unauthenticated use).

- Set a `GITHUB_TOKEN` environment variable.
Any personal access token with no special scopes works — public release data is
publicly readable.

  ```sh
  export GITHUB_TOKEN=ghp_...
  ```

### "Could not parse MAC address from esptool output"

The device responded but the output format was unexpected.

- Try specifying the port explicitly instead of `auto`.
- If you are using an older esptool (v4.x), verify `esptool` is reachable via 
`uv run python -m esptool version`. The tool auto-detects v4/v5 syntax differences.

### Post-flash verification shows nothing

After flashing, the tool connects to the device via serial and sends `show system`.
If nothing is returned:

- The device may still be booting — this is normal on the first flash after a
factory chip. The next flash will succeed.
- The USB port may not support bidirectional serial I/O (some hubs or cables
block it). Verify manually by opening the EMS-ESP WebUI.
- On some platforms the port is briefly locked after flashing. Retry manually
with a serial terminal (`minicom`, `screen`, or PuTTY) on the same port at
115200 baud.

### Firmware cache issues

If the cached firmware appears corrupt or a download was interrupted, force a
fresh download:

```sh
ems-esp-flasher firmware clean
ems-esp-flasher firmware fetch
```

Or re-download a specific board only:

```sh
ems-esp-flasher firmware fetch --board esp32 --force
```

### Find flash size

If the device's flash size is unknown, the esptool can help to determine the
right flash size.

```console
$ uv run esptool flash-id
esptool v5.2.0
Connected to ESP32 on /dev/ttyUSB0:
Chip type:          ESP32-D0WD-V3 (revision v3.1)
Features:           Wi-Fi, BT, Dual Core + LP Core, 240MHz, Vref calibration in eFuse, Coding Scheme None
Crystal frequency:  40MHz
MAC:                <stripped>

Stub flasher running.

Flash Memory Information:
=========================
Manufacturer: 5e
Device: 4016
Detected flash size: 4MB
Flash voltage set by a strapping pin: 3.3V

Hard resetting via RTS pin...
```

Boards are configured in [boards.py](./src/ems_esp_flasher/boards.py) and can be
adjusted if needed.
Do not forget to clean and re-fetch firmware images in case a board
specification is adjusted.

from __future__ import annotations

from unittest.mock import MagicMock, patch

from tests.conftest import (
    PROBE_OUTPUT_V4,
    PROBE_OUTPUT_V5,
    SERIAL_VERIFY_LINES,
    STABLE_RELEASE,
    make_requests_mock,
    make_subprocess_mock,
)


def _serial_ctx(lines: list[bytes]) -> MagicMock:
    """Build a mock serial.Serial context manager that yields the given readline responses."""
    mock_ser = MagicMock()
    mock_ser.readline.side_effect = lines
    mock_cls = MagicMock()
    mock_cls.return_value.__enter__.return_value = mock_ser
    mock_cls.return_value.__exit__.return_value = False
    return mock_cls


class TestFlashIdSubcmdDetection:
    """Unit tests for _flash_id_subcmd() version auto-detection.

    esptool v5 renamed 'flash_id' (underscore) to 'flash-id' (hyphen).
    The function reads the installed esptool version at runtime and returns
    the correct subcommand string so the tool works with both v4 and v5.
    """

    def test_returns_hyphen_form_for_v5(self):
        from ems_esp_flasher.flash import _flash_id_subcmd

        with patch("importlib.metadata.version", return_value="5.0.0"):
            assert _flash_id_subcmd() == "flash-id"

    def test_returns_underscore_form_for_v4(self):
        from ems_esp_flasher.flash import _flash_id_subcmd

        with patch("importlib.metadata.version", return_value="4.9.0"):
            assert _flash_id_subcmd() == "flash_id"

    def test_falls_back_to_underscore_on_version_lookup_failure(self):
        from ems_esp_flasher.flash import _flash_id_subcmd

        with patch("importlib.metadata.version", side_effect=Exception("package not found")):
            assert _flash_id_subcmd() == "flash_id"

    def test_probe_device_passes_hyphen_form_to_subprocess_for_v5(self):
        """probe_device must call esptool with 'flash-id' when v5 is installed."""
        from ems_esp_flasher.flash import probe_device

        mock_run = make_subprocess_mock(probe_output=PROBE_OUTPUT_V5)
        with (
            patch("importlib.metadata.version", return_value="5.0.0"),
            patch("ems_esp_flasher.flash.subprocess.run", mock_run),
        ):
            probe_device("/dev/ttyUSB0")

        cmd = mock_run.call_args[0][0]
        assert "flash-id" in cmd
        assert "flash_id" not in cmd

    def test_probe_device_passes_underscore_form_to_subprocess_for_v4(self):
        """probe_device must call esptool with 'flash_id' when v4 is installed."""
        from ems_esp_flasher.flash import probe_device

        mock_run = make_subprocess_mock(probe_output=PROBE_OUTPUT_V4)
        with (
            patch("importlib.metadata.version", return_value="4.9.0"),
            patch("ems_esp_flasher.flash.subprocess.run", mock_run),
        ):
            probe_device("/dev/ttyUSB0")

        cmd = mock_run.call_args[0][0]
        assert "flash_id" in cmd
        assert "flash-id" not in cmd


class TestFlashErrors:
    def test_unknown_board_exits_with_error(self, runner):
        from ems_esp_flasher.cli import app

        result = runner.invoke(app, ["flash", "esp32c3", "auto"])

        assert result.exit_code == 1
        assert "Unknown board" in result.output

    def test_dev_and_version_are_mutually_exclusive(self, runner):
        from ems_esp_flasher.cli import app

        result = runner.invoke(app, ["flash", "esp32", "auto", "--dev", "--version", "3.7.0"])

        assert result.exit_code == 1
        assert "mutually exclusive" in result.output

    def test_probe_failure_exits_with_error(self, runner, tmp_path):
        from ems_esp_flasher.cli import app

        firmware_file = tmp_path / "EMS-ESP-3_7_0-ESP32-16MB+.bin"
        firmware_file.write_bytes(b"firmware")

        failed_probe = MagicMock()
        failed_probe.returncode = 1
        failed_probe.stdout = ""
        failed_probe.stderr = "Could not connect to device"

        with (
            patch("ems_esp_flasher.github.requests.get", make_requests_mock(STABLE_RELEASE)),
            patch("ems_esp_flasher.flash.subprocess.run", return_value=failed_probe),
        ):
            result = runner.invoke(
                app,
                ["flash", "esp32", "/dev/ttyUSB0", "--firmware-dir", str(tmp_path), "--yes"],
            )

        assert result.exit_code == 1
        assert "Failed to connect" in result.output


class TestFlashHappyPath:
    def test_flash_with_cached_firmware(self, runner, tmp_path):
        """Full flash flow when firmware is already in the local cache."""
        from ems_esp_flasher.cli import app

        # Pre-seed the cache so no download occurs
        firmware_file = tmp_path / "EMS-ESP-3_7_0-ESP32-16MB+.bin"
        firmware_file.write_bytes(b"firmware")

        mock_serial = _serial_ctx(SERIAL_VERIFY_LINES)

        with (
            patch("ems_esp_flasher.github.requests.get", make_requests_mock(STABLE_RELEASE)),
            patch("ems_esp_flasher.flash.subprocess.run", make_subprocess_mock()),
            patch("ems_esp_flasher.flash.serial.Serial", mock_serial),
            patch("ems_esp_flasher.flash.time.sleep"),
            patch("ems_esp_flasher.flash.time.time", side_effect=[0.0, 0.5, 0.6, 0.7, 100.0]),
        ):
            result = runner.invoke(
                app,
                ["flash", "esp32", "/dev/ttyUSB0", "--firmware-dir", str(tmp_path), "--yes"],
            )

        assert result.exit_code == 0
        assert "3.7.0" in result.output
        assert "aa:bb:cc:dd:ee:ff" in result.output
        assert "successfully flashed" in result.output

    def test_flash_auto_fetches_missing_firmware(self, runner, tmp_path):
        """flash downloads firmware automatically when it is not in the cache."""
        from ems_esp_flasher.cli import app

        mock_serial = _serial_ctx(SERIAL_VERIFY_LINES)

        with (
            patch("ems_esp_flasher.github.requests.get", make_requests_mock(STABLE_RELEASE)),
            patch("ems_esp_flasher.flash.subprocess.run", make_subprocess_mock()),
            patch("ems_esp_flasher.flash.serial.Serial", mock_serial),
            patch("ems_esp_flasher.flash.time.sleep"),
            patch("ems_esp_flasher.flash.time.time", side_effect=[0.0, 0.5, 0.6, 0.7, 100.0]),
        ):
            result = runner.invoke(
                app,
                ["flash", "esp32", "/dev/ttyUSB0", "--firmware-dir", str(tmp_path), "--yes"],
            )

        assert result.exit_code == 0
        # Firmware was downloaded into the cache
        assert (tmp_path / "EMS-ESP-3_7_0-ESP32-16MB+.bin").exists()
        assert "fetching" in result.output.lower()

    def test_flash_shows_confirmation_summary(self, runner, tmp_path):
        """The confirmation prompt displays all relevant flash parameters."""
        from ems_esp_flasher.cli import app

        firmware_file = tmp_path / "EMS-ESP-3_7_0-ESP32-16MB+.bin"
        firmware_file.write_bytes(b"firmware")

        mock_serial = _serial_ctx([b""])

        with (
            patch("ems_esp_flasher.github.requests.get", make_requests_mock(STABLE_RELEASE)),
            patch("ems_esp_flasher.flash.subprocess.run", make_subprocess_mock()),
            patch("ems_esp_flasher.flash.serial.Serial", mock_serial),
            patch("ems_esp_flasher.flash.time.sleep"),
            patch("ems_esp_flasher.flash.time.time", side_effect=[0.0, 100.0]),
        ):
            result = runner.invoke(
                app,
                ["flash", "esp32", "/dev/ttyUSB0", "--firmware-dir", str(tmp_path), "--yes"],
            )

        assert "Board:" in result.output
        assert "Port:" in result.output
        assert "MAC address:" in result.output
        assert "Firmware version:" in result.output
        assert "MCU:" in result.output

    def test_flash_shows_verification_info(self, runner, tmp_path):
        """Version and board info returned by serial verification appear in output."""
        from ems_esp_flasher.cli import app

        firmware_file = tmp_path / "EMS-ESP-3_7_0-ESP32-16MB+.bin"
        firmware_file.write_bytes(b"firmware")

        mock_serial = _serial_ctx(SERIAL_VERIFY_LINES)

        with (
            patch("ems_esp_flasher.github.requests.get", make_requests_mock(STABLE_RELEASE)),
            patch("ems_esp_flasher.flash.subprocess.run", make_subprocess_mock()),
            patch("ems_esp_flasher.flash.serial.Serial", mock_serial),
            patch("ems_esp_flasher.flash.time.sleep"),
            patch("ems_esp_flasher.flash.time.time", side_effect=[0.0, 0.5, 0.6, 0.7, 100.0]),
        ):
            result = runner.invoke(
                app,
                ["flash", "esp32", "/dev/ttyUSB0", "--firmware-dir", str(tmp_path), "--yes"],
            )

        assert result.exit_code == 0
        assert "Version: 3.7.0" in result.output
        assert "Board profile: esp32" in result.output

    def test_flash_warns_when_verification_produces_no_output(self, runner, tmp_path):
        """A yellow warning is shown when post-flash serial read returns nothing."""
        from ems_esp_flasher.cli import app

        firmware_file = tmp_path / "EMS-ESP-3_7_0-ESP32-16MB+.bin"
        firmware_file.write_bytes(b"firmware")

        # Serial yields only empty bytes — no device info
        mock_serial = _serial_ctx([b""])

        with (
            patch("ems_esp_flasher.github.requests.get", make_requests_mock(STABLE_RELEASE)),
            patch("ems_esp_flasher.flash.subprocess.run", make_subprocess_mock()),
            patch("ems_esp_flasher.flash.serial.Serial", mock_serial),
            patch("ems_esp_flasher.flash.time.sleep"),
            patch("ems_esp_flasher.flash.time.time", side_effect=[0.0, 100.0]),
        ):
            result = runner.invoke(
                app,
                ["flash", "esp32", "/dev/ttyUSB0", "--firmware-dir", str(tmp_path), "--yes"],
            )

        assert result.exit_code == 0
        assert "verify manually" in result.output

    def test_flash_parses_esptool_v4_probe_output(self, runner, tmp_path):
        """Port and MAC are correctly parsed from esptool v4 output format."""
        from ems_esp_flasher.cli import app

        firmware_file = tmp_path / "EMS-ESP-3_7_0-ESP32-16MB+.bin"
        firmware_file.write_bytes(b"firmware")

        mock_serial = _serial_ctx([b""])

        with (
            patch("ems_esp_flasher.github.requests.get", make_requests_mock(STABLE_RELEASE)),
            patch("ems_esp_flasher.flash.subprocess.run", make_subprocess_mock(probe_output=PROBE_OUTPUT_V4)),
            patch("ems_esp_flasher.flash.serial.Serial", mock_serial),
            patch("ems_esp_flasher.flash.time.sleep"),
            patch("ems_esp_flasher.flash.time.time", side_effect=[0.0, 100.0]),
        ):
            result = runner.invoke(
                app,
                ["flash", "esp32", "/dev/ttyUSB0", "--firmware-dir", str(tmp_path), "--yes"],
            )

        assert result.exit_code == 0
        assert "aa:bb:cc:dd:ee:ff" in result.output
        assert "/dev/ttyUSB0" in result.output

    def test_flash_serial_exception_during_verify_is_non_fatal(self, runner, tmp_path):
        """A SerialException during post-flash verification does not fail the command."""
        from ems_esp_flasher.cli import app
        import serial as pyserial

        firmware_file = tmp_path / "EMS-ESP-3_7_0-ESP32-16MB+.bin"
        firmware_file.write_bytes(b"firmware")

        mock_serial_cls = MagicMock()
        mock_serial_cls.return_value.__enter__.side_effect = pyserial.SerialException("port busy")

        with (
            patch("ems_esp_flasher.github.requests.get", make_requests_mock(STABLE_RELEASE)),
            patch("ems_esp_flasher.flash.subprocess.run", make_subprocess_mock()),
            patch("ems_esp_flasher.flash.serial.Serial", mock_serial_cls),
            patch("ems_esp_flasher.flash.time.sleep"),
        ):
            result = runner.invoke(
                app,
                ["flash", "esp32", "/dev/ttyUSB0", "--firmware-dir", str(tmp_path), "--yes"],
            )

        assert result.exit_code == 0
        assert "verify manually" in result.output

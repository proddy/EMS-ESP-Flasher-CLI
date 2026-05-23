from __future__ import annotations

from unittest.mock import patch

from tests.conftest import (
    STABLE_RELEASE,
    DEV_RELEASE,
    make_requests_mock,
)


class TestFirmwareFetch:
    def test_downloads_both_boards_by_default(self, runner, tmp_path):
        from ems_esp_flasher.cli import app

        with patch("ems_esp_flasher.github.requests.get", make_requests_mock(STABLE_RELEASE)):
            result = runner.invoke(
                app,
                ["firmware", "fetch", "--firmware-dir", str(tmp_path)],
            )

        assert result.exit_code == 0
        assert (tmp_path / "EMS-ESP-3_7_0-ESP32-16MB+.bin").exists()
        assert (tmp_path / "EMS-ESP-3_7_0-ESP32S3-16MB+.bin").exists()
        assert "Firmware fetch complete." in result.output

    def test_downloads_single_board_with_board_flag(self, runner, tmp_path):
        from ems_esp_flasher.cli import app

        with patch("ems_esp_flasher.github.requests.get", make_requests_mock(STABLE_RELEASE)):
            result = runner.invoke(
                app,
                ["firmware", "fetch", "--board", "esp32", "--firmware-dir", str(tmp_path)],
            )

        assert result.exit_code == 0
        assert (tmp_path / "EMS-ESP-3_7_0-ESP32-16MB+.bin").exists()
        assert not (tmp_path / "EMS-ESP-3_7_0-ESP32S3-16MB+.bin").exists()

    def test_skips_already_cached_files(self, runner, tmp_path):
        from ems_esp_flasher.cli import app

        # Pre-create both firmware files
        esp32_file = tmp_path / "EMS-ESP-3_7_0-ESP32-16MB+.bin"
        esp32s3_file = tmp_path / "EMS-ESP-3_7_0-ESP32S3-16MB+.bin"
        esp32_file.write_bytes(b"original_content")
        esp32s3_file.write_bytes(b"original_content")

        mock_get = make_requests_mock(STABLE_RELEASE)
        with patch("ems_esp_flasher.github.requests.get", mock_get):
            result = runner.invoke(
                app,
                ["firmware", "fetch", "--firmware-dir", str(tmp_path)],
            )

        assert result.exit_code == 0
        assert "already cached" in result.output
        # Files should not have been overwritten
        assert esp32_file.read_bytes() == b"original_content"
        assert esp32s3_file.read_bytes() == b"original_content"
        # Only the metadata call should have been made (no stream downloads)
        stream_calls = [
            c for c in mock_get.call_args_list if c.kwargs.get("stream")
        ]
        assert len(stream_calls) == 0

    def test_force_redownloads_cached_files(self, runner, tmp_path):
        from ems_esp_flasher.cli import app

        esp32_file = tmp_path / "EMS-ESP-3_7_0-ESP32-16MB+.bin"
        esp32_file.write_bytes(b"original_content")

        with patch("ems_esp_flasher.github.requests.get", make_requests_mock(STABLE_RELEASE)):
            result = runner.invoke(
                app,
                [
                    "firmware", "fetch",
                    "--board", "esp32",
                    "--force",
                    "--firmware-dir", str(tmp_path),
                ],
            )

        assert result.exit_code == 0
        assert esp32_file.read_bytes() == b"fake_firmware_content"

    def test_dev_flag_fetches_dev_release(self, runner, tmp_path):
        from ems_esp_flasher.cli import app

        with patch("ems_esp_flasher.github.requests.get", make_requests_mock(DEV_RELEASE)):
            result = runner.invoke(
                app,
                ["firmware", "fetch", "--dev", "--board", "esp32", "--firmware-dir", str(tmp_path)],
            )

        assert result.exit_code == 0
        assert "Development Build" in result.output
        assert (tmp_path / "EMS-ESP-3_8_0-dev-ESP32-16MB+.bin").exists()

    def test_dev_and_version_are_mutually_exclusive(self, runner, tmp_path):
        from ems_esp_flasher.cli import app

        result = runner.invoke(
            app,
            ["firmware", "fetch", "--dev", "--version", "3.7.0", "--firmware-dir", str(tmp_path)],
        )

        assert result.exit_code == 1
        assert "mutually exclusive" in result.output

    def test_unknown_board_exits_with_error(self, runner, tmp_path):
        from ems_esp_flasher.cli import app

        result = runner.invoke(
            app,
            ["firmware", "fetch", "--board", "esp32c3", "--firmware-dir", str(tmp_path)],
        )

        assert result.exit_code == 1
        assert "Unknown board" in result.output


class TestFirmwareClean:
    def test_deletes_firmware_directory(self, runner, tmp_path):
        from ems_esp_flasher.cli import app

        firmware_dir = tmp_path / "firmware"
        firmware_dir.mkdir()
        (firmware_dir / "some_firmware.bin").write_bytes(b"data")

        result = runner.invoke(
            app,
            ["firmware", "clean", "--firmware-dir", str(firmware_dir)],
            input="y\n",
        )

        assert result.exit_code == 0
        assert not firmware_dir.exists()
        assert "Deleted" in result.output

    def test_handles_nonexistent_directory_gracefully(self, runner, tmp_path):
        from ems_esp_flasher.cli import app

        missing_dir = tmp_path / "does_not_exist"

        result = runner.invoke(
            app,
            ["firmware", "clean", "--firmware-dir", str(missing_dir)],
        )

        assert result.exit_code == 0
        assert "does not exist" in result.output

    def test_abort_on_no_confirmation(self, runner, tmp_path):
        from ems_esp_flasher.cli import app

        firmware_dir = tmp_path / "firmware"
        firmware_dir.mkdir()
        (firmware_dir / "some_firmware.bin").write_bytes(b"data")

        result = runner.invoke(
            app,
            ["firmware", "clean", "--firmware-dir", str(firmware_dir)],
            input="n\n",
        )

        assert result.exit_code != 0
        assert firmware_dir.exists()

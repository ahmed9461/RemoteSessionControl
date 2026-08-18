from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from core.distribution import (
    WINDOWS_BUILD_MANIFEST,
    WINDOWS_EXE,
    WINDOWS_PORTABLE_ZIP,
    WINDOWS_RECORDING_HELPER,
    artifact_path,
    distribution_manifest,
    render_session_batch_launcher,
    render_session_cmd_wrapper,
    render_session_powershell_launcher,
)


def test_distribution_manifest_reports_available_files(tmp_path: Path) -> None:
    exe = tmp_path / WINDOWS_EXE
    exe.write_bytes(b"test-client")
    portable = tmp_path / WINDOWS_PORTABLE_ZIP
    portable.write_bytes(b"test-portable")
    recorder = tmp_path / WINDOWS_RECORDING_HELPER
    recorder.write_bytes(b"test-recorder")
    build_manifest = tmp_path / WINDOWS_BUILD_MANIFEST
    build_manifest.write_text("{}", encoding="utf-8")
    launcher = tmp_path / "Start-RemoteSession.ps1"
    launcher.write_text("Write-Host test", encoding="utf-8")

    manifest = distribution_manifest(str(tmp_path), "https://control.example.com")

    assert manifest["remote_https_ready"] is True
    assert manifest["windows"]["exe"]["available"] is True
    assert manifest["windows"]["portable"]["available"] is True
    assert manifest["windows"]["recording_helper"]["available"] is True
    assert manifest["windows"]["build_manifest"]["available"] is True
    assert manifest["windows"]["batch_ready"] is True
    assert manifest["windows"]["cmd_ready"] is True
    assert manifest["windows"]["powershell_ready"] is True
    assert manifest["windows"]["exe"]["sha256"] == hashlib.sha256(b"test-client").hexdigest()
    assert manifest["windows"]["exe"]["url"].endswith("/downloads/RemoteSessionControl-Client.exe")


def test_download_allowlist_rejects_unknown_names_and_allows_manifest(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        artifact_path(str(tmp_path), "../../etc/passwd")
    with pytest.raises(ValueError):
        artifact_path(str(tmp_path), "anything.exe")
    assert artifact_path(str(tmp_path), WINDOWS_BUILD_MANIFEST).name == WINDOWS_BUILD_MANIFEST


def test_session_powershell_launcher_binds_https_server_code_url_and_hash() -> None:
    sha = "a" * 64
    script = render_session_powershell_launcher(
        server_url="https://control.example.com",
        pairing_code="ABCD-2345",
        client_url="https://control.example.com/downloads/RemoteSessionControl-Client.exe",
        expected_sha256=sha,
    )

    assert "$Server = 'https://control.example.com'" in script
    assert "$PairingCode = 'ABCD-2345'" in script
    assert "Get-FileHash" in script
    assert "curl.exe" in script
    assert "--progress-bar" in script
    assert "Start-Process" in script


def test_batch_launcher_is_one_click_and_does_not_use_powershell() -> None:
    script = render_session_batch_launcher(
        server_url="https://control.example.com",
        pairing_code="ABCD-2345",
        client_url="https://control.example.com/downloads/RemoteSessionControl-Client.exe",
        expected_sha256="b" * 64,
    )

    assert "curl.exe" in script
    assert "certutil.exe" in script
    assert "start \"RemoteSessionControl\"" in script
    assert "powershell.exe" not in script.lower()
    assert "ABCD-2345" in script


def test_cmd_wrapper_uses_process_only_execution_policy_bypass() -> None:
    script = render_session_cmd_wrapper(
        server_url="https://control.example.com",
        pairing_code="ABCD-2345",
        client_url="https://control.example.com/downloads/RemoteSessionControl-Client.exe",
        client_sha256="c" * 64,
        powershell_url="https://control.example.com/downloads/Start-RemoteSession.ps1",
        powershell_sha256="d" * 64,
    )

    assert "powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File" in script
    assert "does not change the machine or user Execution Policy" in script
    assert "certutil.exe" in script
    assert "ABCD-2345" in script


def test_launchers_reject_insecure_remote_urls() -> None:
    with pytest.raises(ValueError):
        render_session_powershell_launcher(
            server_url="http://control.example.com",
            pairing_code="ABCD-2345",
            client_url="https://control.example.com/client.exe",
            expected_sha256="e" * 64,
        )
    with pytest.raises(ValueError):
        render_session_batch_launcher(
            server_url="https://control.example.com",
            pairing_code="ABCD-2345",
            client_url="http://control.example.com/client.exe",
            expected_sha256="f" * 64,
        )

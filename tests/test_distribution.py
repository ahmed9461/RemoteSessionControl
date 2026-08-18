from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from core.distribution import (
    WINDOWS_EXE,
    WINDOWS_PORTABLE_ZIP,
    artifact_path,
    distribution_manifest,
    render_session_powershell_launcher,
)


def test_distribution_manifest_reports_available_files(tmp_path: Path) -> None:
    exe = tmp_path / WINDOWS_EXE
    exe.write_bytes(b"test-client")
    portable = tmp_path / WINDOWS_PORTABLE_ZIP
    portable.write_bytes(b"test-portable")

    manifest = distribution_manifest(str(tmp_path), "https://control.example.com")

    assert manifest["remote_https_ready"] is True
    assert manifest["windows"]["exe"]["available"] is True
    assert manifest["windows"]["portable"]["available"] is True
    assert manifest["windows"]["powershell_ready"] is True
    assert manifest["windows"]["exe"]["sha256"] == hashlib.sha256(b"test-client").hexdigest()
    assert manifest["windows"]["exe"]["url"].endswith("/downloads/RemoteSessionControl-Client.exe")


def test_download_allowlist_rejects_unknown_names(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        artifact_path(str(tmp_path), "../../etc/passwd")
    with pytest.raises(ValueError):
        artifact_path(str(tmp_path), "anything.exe")


def test_session_launcher_binds_https_server_code_url_and_hash() -> None:
    sha = "a" * 64
    script = render_session_powershell_launcher(
        server_url="https://control.example.com",
        pairing_code="ABCD2345",
        client_url="https://control.example.com/downloads/RemoteSessionControl-Client.exe",
        expected_sha256=sha,
    )

    assert "$Server = 'https://control.example.com'" in script
    assert "$PairingCode = 'ABCD2345'" in script
    assert "Get-FileHash" in script
    assert "Start-Process" in script
    assert "Scheduled Task" not in script


def test_session_launcher_rejects_insecure_remote_urls() -> None:
    with pytest.raises(ValueError):
        render_session_powershell_launcher(
            server_url="http://control.example.com",
            pairing_code="ABCD2345",
            client_url="https://control.example.com/client.exe",
            expected_sha256="b" * 64,
        )

from __future__ import annotations

import hashlib
import re
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote, urlparse

WINDOWS_EXE = "RemoteSessionControl-Client.exe"
WINDOWS_PORTABLE_ZIP = "RemoteSessionControl-Windows-Portable.zip"
WINDOWS_RECORDING_HELPER = "RemoteSessionControl-FFmpeg.exe"
POWERSHELL_LAUNCHER = "Start-RemoteSession.ps1"

ALLOWED_DOWNLOADS = {
    WINDOWS_EXE,
    WINDOWS_PORTABLE_ZIP,
    WINDOWS_RECORDING_HELPER,
    POWERSHELL_LAUNCHER,
}


def artifact_path(downloads_dir: str, filename: str) -> Path:
    if filename not in ALLOWED_DOWNLOADS:
        raise ValueError("unsupported download artifact")
    base = Path(downloads_dir).resolve()
    path = (base / filename).resolve()
    if path.parent != base:
        raise ValueError("invalid download path")
    return path


@lru_cache(maxsize=64)
def _sha256_cached(path_text: str, mtime_ns: int, size: int) -> str:
    del mtime_ns, size
    digest = hashlib.sha256()
    with Path(path_text).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_file(path: Path) -> str:
    stat = path.stat()
    return _sha256_cached(str(path.resolve()), stat.st_mtime_ns, stat.st_size)


def public_download_url(public_base_url: str, filename: str) -> str:
    return f"{public_base_url.rstrip('/')}/downloads/{quote(filename)}"


def is_remote_https(public_base_url: str) -> bool:
    return public_base_url.lower().startswith("https://")


def artifact_metadata(downloads_dir: str, public_base_url: str, filename: str) -> dict:
    path = artifact_path(downloads_dir, filename)
    if not path.is_file():
        return {
            "filename": filename,
            "available": False,
            "url": None,
            "sha256": None,
            "size_bytes": 0,
        }
    return {
        "filename": filename,
        "available": True,
        "url": public_download_url(public_base_url, filename),
        "sha256": sha256_file(path),
        "size_bytes": path.stat().st_size,
    }


def distribution_manifest(downloads_dir: str, public_base_url: str) -> dict:
    exe = artifact_metadata(downloads_dir, public_base_url, WINDOWS_EXE)
    portable = artifact_metadata(downloads_dir, public_base_url, WINDOWS_PORTABLE_ZIP)
    recorder = artifact_metadata(downloads_dir, public_base_url, WINDOWS_RECORDING_HELPER)
    launcher = artifact_metadata(downloads_dir, public_base_url, POWERSHELL_LAUNCHER)
    exe_ready = bool(exe["available"] and exe["url"] and exe["sha256"])
    powershell_ready = bool(exe_ready and launcher["available"] and launcher["url"] and launcher["sha256"])
    return {
        "public_base_url": public_base_url.rstrip("/"),
        "remote_https_ready": is_remote_https(public_base_url),
        "windows": {
            "exe": exe,
            "portable": portable,
            "recording_helper": recorder,
            "powershell_launcher": launcher,
            "batch_ready": exe_ready,
            "cmd_ready": powershell_ready,
            "powershell_ready": exe_ready,
        },
    }


def _validate_https_url(value: str, label: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme.lower() != "https" or not parsed.netloc:
        raise ValueError(f"{label} requires an HTTPS URL")
    if parsed.username or parsed.password or parsed.fragment:
        raise ValueError(f"invalid {label} URL")
    return value


def _validate_sha256(value: str) -> str:
    value = value.strip().lower()
    if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
        raise ValueError("invalid SHA-256")
    return value


def _validate_pairing_code(value: str) -> str:
    value = value.strip().upper()
    if not re.fullmatch(r"[A-Z0-9-]{4,32}", value):
        raise ValueError("invalid pairing code")
    return value


def _ps_single_quote(value: str) -> str:
    return value.replace("'", "''")


def _batch_value(value: str, label: str) -> str:
    if any(char in value for char in ('"', "%", "!", "\r", "\n", "&", "|", "<", ">", "^")):
        raise ValueError(f"unsupported character in {label}")
    return value


def render_session_powershell_launcher(
    *,
    server_url: str,
    pairing_code: str,
    client_url: str,
    expected_sha256: str,
) -> str:
    """Render a visible, temporary PowerShell launcher for one pairing session."""

    server_url = _validate_https_url(server_url.rstrip("/"), "session PowerShell launcher")
    client_url = _validate_https_url(client_url, "session PowerShell client")
    pairing_code = _validate_pairing_code(pairing_code)
    expected_sha256 = _validate_sha256(expected_sha256)

    server = _ps_single_quote(server_url)
    code = _ps_single_quote(pairing_code)
    url = _ps_single_quote(client_url)
    sha = expected_sha256

    return f"""[CmdletBinding()]\nparam()\n\nSet-StrictMode -Version Latest\n$ErrorActionPreference = 'Stop'\n\n$Server = '{server}'\n$PairingCode = '{code}'\n$ClientUrl = '{url}'\n$ExpectedSha256 = '{sha}'\n\n$workDir = Join-Path $env:TEMP 'RemoteSessionControl'\nNew-Item -ItemType Directory -Force -Path $workDir | Out-Null\n$client = Join-Path $workDir 'RemoteSessionControl-Client.exe'\n\n$needsDownload = $true\nif (Test-Path -LiteralPath $client) {{\n    $existingHash = (Get-FileHash -LiteralPath $client -Algorithm SHA256).Hash.ToLowerInvariant()\n    if ($existingHash -eq $ExpectedSha256) {{\n        $needsDownload = $false\n        Write-Host 'Using the already downloaded verified client.'\n    }}\n}}\n\nif ($needsDownload) {{\n    Write-Host 'Downloading the RemoteSessionControl temporary client...'\n    $curl = Get-Command curl.exe -ErrorAction SilentlyContinue\n    if ($curl) {{\n        & $curl.Source --fail --location --retry 3 --retry-delay 2 --connect-timeout 15 --progress-bar --output $client $ClientUrl\n        if ($LASTEXITCODE -ne 0) {{\n            Remove-Item -LiteralPath $client -Force -ErrorAction SilentlyContinue\n            throw \"Client download failed (curl exit code $LASTEXITCODE).\"\n        }}\n    }} else {{\n        Write-Host 'curl.exe was not found; falling back to Invoke-WebRequest.'\n        Invoke-WebRequest -Uri $ClientUrl -OutFile $client -UseBasicParsing\n    }}\n}}\n\n$actualHash = (Get-FileHash -LiteralPath $client -Algorithm SHA256).Hash.ToLowerInvariant()\nif ($actualHash -ne $ExpectedSha256) {{\n    Remove-Item -LiteralPath $client -Force -ErrorAction SilentlyContinue\n    throw \"Client SHA-256 verification failed. Expected $ExpectedSha256 but got $actualHash.\"\n}}\n\nWrite-Host 'Client SHA-256 verified.'\nWrite-Host 'Starting a visible temporary session client. The client will ask for local consent.'\n\n$arguments = @('--server', $Server, '--pairing-code', $PairingCode)\n$process = Start-Process -FilePath $client -ArgumentList $arguments -PassThru\n$PairingCode = $null\nWrite-Host \"Client started (PID $($process.Id)). You may close this PowerShell window.\"\nWrite-Host 'No service, startup entry, scheduled task, or hidden persistence was installed.'\n"""


def render_session_batch_launcher(
    *,
    server_url: str,
    pairing_code: str,
    client_url: str,
    expected_sha256: str,
) -> str:
    """Render a pure CMD/BAT one-click launcher without changing PowerShell policy."""

    server = _batch_value(_validate_https_url(server_url.rstrip("/"), "BAT launcher"), "server URL")
    code = _batch_value(_validate_pairing_code(pairing_code), "pairing code")
    url = _batch_value(_validate_https_url(client_url, "BAT client"), "client URL")
    sha = _batch_value(_validate_sha256(expected_sha256), "SHA-256")

    return f"""@echo off\r\nsetlocal EnableExtensions EnableDelayedExpansion\r\ntitle RemoteSessionControl - Temporary Session\r\nset \"SERVER={server}\"\r\nset \"PAIRING_CODE={code}\"\r\nset \"CLIENT_URL={url}\"\r\nset \"EXPECTED_SHA256={sha}\"\r\nset \"WORK_DIR=%TEMP%\\RemoteSessionControl\"\r\nset \"CLIENT=%WORK_DIR%\\RemoteSessionControl-Client.exe\"\r\n\r\nif not exist \"%WORK_DIR%\" mkdir \"%WORK_DIR%\" >nul 2>nul\r\nwhere curl.exe >nul 2>nul || goto :missing_curl\r\nwhere certutil.exe >nul 2>nul || goto :missing_certutil\r\n\r\ncall :verify_client\r\nif !errorlevel! equ 0 (\r\n    echo Using the already downloaded verified client.\r\n    goto :launch\r\n)\r\n\r\nif exist \"%CLIENT%\" del /q \"%CLIENT%\" >nul 2>nul\r\necho Downloading the RemoteSessionControl temporary client...\r\ncurl.exe --fail --location --retry 3 --retry-delay 2 --connect-timeout 15 --progress-bar --output \"%CLIENT%\" \"%CLIENT_URL%\"\r\nif errorlevel 1 goto :download_failed\r\n\r\ncall :verify_client\r\nif errorlevel 1 goto :hash_failed\r\n\r\n:launch\r\necho Client SHA-256 verified.\r\necho Starting the visible temporary client. Local consent is still required.\r\nstart \"RemoteSessionControl\" \"%CLIENT%\" --server \"%SERVER%\" --pairing-code \"%PAIRING_CODE%\"\r\nset \"PAIRING_CODE=\"\r\necho No service, Startup entry, scheduled task, or persistence was installed.\r\nexit /b 0\r\n\r\n:verify_client\r\nif not exist \"%CLIENT%\" exit /b 1\r\nset \"ACTUAL_SHA256=\"\r\nfor /f \"skip=1 tokens=* delims=\" %%H in ('certutil.exe -hashfile \"%CLIENT%\" SHA256 2^>nul') do (\r\n    if not defined ACTUAL_SHA256 set \"ACTUAL_SHA256=%%H\"\r\n)\r\nif not defined ACTUAL_SHA256 exit /b 1\r\nset \"ACTUAL_SHA256=!ACTUAL_SHA256: =!\"\r\nif /i \"!ACTUAL_SHA256!\"==\"%EXPECTED_SHA256%\" exit /b 0\r\nexit /b 1\r\n\r\n:missing_curl\r\necho ERROR: curl.exe is required on this Windows installation.\r\ngoto :failed\r\n\r\n:missing_certutil\r\necho ERROR: certutil.exe is required to verify SHA-256.\r\ngoto :failed\r\n\r\n:download_failed\r\nif exist \"%CLIENT%\" del /q \"%CLIENT%\" >nul 2>nul\r\necho ERROR: Client download failed.\r\ngoto :failed\r\n\r\n:hash_failed\r\nif exist \"%CLIENT%\" del /q \"%CLIENT%\" >nul 2>nul\r\necho ERROR: Client SHA-256 verification failed.\r\ngoto :failed\r\n\r\n:failed\r\nset \"PAIRING_CODE=\"\r\necho.\r\npause\r\nexit /b 1\r\n"""


def render_session_cmd_wrapper(
    *,
    server_url: str,
    pairing_code: str,
    client_url: str,
    client_sha256: str,
    powershell_url: str,
    powershell_sha256: str,
) -> str:
    """Render a one-click CMD wrapper that runs the verified PS1 with process-only Bypass."""

    server = _batch_value(_validate_https_url(server_url.rstrip("/"), "CMD wrapper"), "server URL")
    code = _batch_value(_validate_pairing_code(pairing_code), "pairing code")
    client_url = _batch_value(_validate_https_url(client_url, "CMD client"), "client URL")
    client_sha = _batch_value(_validate_sha256(client_sha256), "client SHA-256")
    ps_url = _batch_value(_validate_https_url(powershell_url, "CMD PowerShell launcher"), "PowerShell URL")
    ps_sha = _batch_value(_validate_sha256(powershell_sha256), "PowerShell SHA-256")

    return f"""@echo off\r\nsetlocal EnableExtensions EnableDelayedExpansion\r\ntitle RemoteSessionControl - PowerShell Compatibility Launcher\r\nset \"SERVER={server}\"\r\nset \"PAIRING_CODE={code}\"\r\nset \"CLIENT_URL={client_url}\"\r\nset \"CLIENT_SHA256={client_sha}\"\r\nset \"PS_URL={ps_url}\"\r\nset \"PS_SHA256={ps_sha}\"\r\nset \"WORK_DIR=%TEMP%\\RemoteSessionControl\"\r\nset \"PS_SCRIPT=%WORK_DIR%\\Start-RemoteSession.ps1\"\r\n\r\nif not exist \"%WORK_DIR%\" mkdir \"%WORK_DIR%\" >nul 2>nul\r\nwhere curl.exe >nul 2>nul || goto :missing_tool\r\nwhere certutil.exe >nul 2>nul || goto :missing_tool\r\nwhere powershell.exe >nul 2>nul || goto :missing_tool\r\n\r\necho Preparing the temporary PowerShell launcher...\r\ncurl.exe --fail --location --retry 3 --retry-delay 2 --connect-timeout 15 --silent --show-error --output \"%PS_SCRIPT%\" \"%PS_URL%\"\r\nif errorlevel 1 goto :failed\r\n\r\nset \"ACTUAL_PS_SHA256=\"\r\nfor /f \"skip=1 tokens=* delims=\" %%H in ('certutil.exe -hashfile \"%PS_SCRIPT%\" SHA256 2^>nul') do (\r\n    if not defined ACTUAL_PS_SHA256 set \"ACTUAL_PS_SHA256=%%H\"\r\n)\r\nif not defined ACTUAL_PS_SHA256 goto :failed\r\nset \"ACTUAL_PS_SHA256=!ACTUAL_PS_SHA256: =!\"\r\nif /i not \"!ACTUAL_PS_SHA256!\"==\"%PS_SHA256%\" (\r\n    echo ERROR: PowerShell launcher SHA-256 verification failed.\r\n    del /q \"%PS_SCRIPT%\" >nul 2>nul\r\n    goto :failed\r\n)\r\n\r\necho Launching with a process-only PowerShell ExecutionPolicy Bypass.\r\necho This does not change the machine or user Execution Policy.\r\npowershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File \"%PS_SCRIPT%\" -Server \"%SERVER%\" -PairingCode \"%PAIRING_CODE%\" -ClientUrl \"%CLIENT_URL%\" -ExpectedSha256 \"%CLIENT_SHA256%\"\r\nset \"RESULT=%ERRORLEVEL%\"\r\nset \"PAIRING_CODE=\"\r\nif not \"%RESULT%\"==\"0\" goto :failed\r\nexit /b 0\r\n\r\n:missing_tool\r\necho ERROR: This compatibility launcher requires curl.exe, certutil.exe, and powershell.exe.\r\n\r\n:failed\r\nset \"PAIRING_CODE=\"\r\necho.\r\npause\r\nexit /b 1\r\n"""

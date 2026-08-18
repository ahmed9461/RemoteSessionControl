from __future__ import annotations

import hashlib
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

WINDOWS_EXE = "RemoteSessionControl-Client.exe"
WINDOWS_PORTABLE_ZIP = "RemoteSessionControl-Windows-Portable.zip"
POWERSHELL_LAUNCHER = "Start-RemoteSession.ps1"

ALLOWED_DOWNLOADS = {
    WINDOWS_EXE,
    WINDOWS_PORTABLE_ZIP,
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
    launcher = artifact_metadata(downloads_dir, public_base_url, POWERSHELL_LAUNCHER)
    return {
        "public_base_url": public_base_url.rstrip("/"),
        "remote_https_ready": is_remote_https(public_base_url),
        "windows": {
            "exe": exe,
            "portable": portable,
            "powershell_launcher": launcher,
            "powershell_ready": bool(exe["available"]),
        },
    }


def _ps_single_quote(value: str) -> str:
    return value.replace("'", "''")


def render_session_powershell_launcher(
    *,
    server_url: str,
    pairing_code: str,
    client_url: str,
    expected_sha256: str,
) -> str:
    """Render a visible, temporary PowerShell launcher for one pairing session.

    The launcher downloads the same Windows client over HTTPS, verifies SHA-256,
    and starts it as a separate visible process. It does not install persistence.
    """

    if not server_url.lower().startswith("https://"):
        raise ValueError("session PowerShell launcher requires an HTTPS server URL")
    if not client_url.lower().startswith("https://"):
        raise ValueError("session PowerShell launcher requires an HTTPS client URL")
    if len(expected_sha256) != 64 or any(c not in "0123456789abcdefABCDEF" for c in expected_sha256):
        raise ValueError("invalid SHA-256")

    server = _ps_single_quote(server_url.rstrip("/"))
    code = _ps_single_quote(pairing_code.strip().upper())
    url = _ps_single_quote(client_url)
    sha = expected_sha256.lower()

    return f"""[CmdletBinding()]\nparam()\n\nSet-StrictMode -Version Latest\n$ErrorActionPreference = 'Stop'\n\n$Server = '{server}'\n$PairingCode = '{code}'\n$ClientUrl = '{url}'\n$ExpectedSha256 = '{sha}'\n\nif (-not $Server.StartsWith('https://', [System.StringComparison]::OrdinalIgnoreCase)) {{\n    throw 'This launcher requires HTTPS.'\n}}\n\n$workDir = Join-Path $env:TEMP 'RemoteSessionControl'\nNew-Item -ItemType Directory -Force -Path $workDir | Out-Null\n$client = Join-Path $workDir 'RemoteSessionControl-Client.exe'\n\n$needsDownload = $true\nif (Test-Path -LiteralPath $client) {{\n    $existingHash = (Get-FileHash -LiteralPath $client -Algorithm SHA256).Hash.ToLowerInvariant()\n    if ($existingHash -eq $ExpectedSha256) {{\n        $needsDownload = $false\n        Write-Host 'Using the already downloaded verified client.'\n    }}\n}}\n\nif ($needsDownload) {{\n    Write-Host 'Downloading the RemoteSessionControl temporary client (~64 MB)...'\n    $curl = Get-Command curl.exe -ErrorAction SilentlyContinue\n    if ($curl) {{\n        & $curl.Source --fail --location --retry 3 --retry-delay 2 --connect-timeout 15 --progress-bar --output $client $ClientUrl\n        if ($LASTEXITCODE -ne 0) {{\n            Remove-Item -LiteralPath $client -Force -ErrorAction SilentlyContinue\n            throw \"Client download failed (curl exit code $LASTEXITCODE).\"\n        }}\n    }} else {{\n        Write-Host 'curl.exe was not found; falling back to Invoke-WebRequest.'\n        Invoke-WebRequest -Uri $ClientUrl -OutFile $client -UseBasicParsing\n    }}\n}}\n\n$actualHash = (Get-FileHash -LiteralPath $client -Algorithm SHA256).Hash.ToLowerInvariant()\nif ($actualHash -ne $ExpectedSha256) {{\n    Remove-Item -LiteralPath $client -Force -ErrorAction SilentlyContinue\n    throw \"Client SHA-256 verification failed. Expected $ExpectedSha256 but got $actualHash.\"\n}}\n\nWrite-Host 'Client SHA-256 verified.'\nWrite-Host 'Starting a visible temporary session client. The client will ask for local consent.'\n\n$arguments = @('--server', $Server, '--pairing-code', $PairingCode)\n$process = Start-Process -FilePath $client -ArgumentList $arguments -PassThru\n$PairingCode = $null\nWrite-Host \"Client started (PID $($process.Id)). You may close this PowerShell window.\"\nWrite-Host 'No service, startup entry, scheduled task, or hidden persistence was installed.'\n"""

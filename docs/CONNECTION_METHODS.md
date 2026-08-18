# Windows connection methods

RemoteSessionControl intentionally supports multiple ways to start the **same temporary device client session**. These are not separate security models or separate remote-control systems. They all use the same Protocol v1, pairing rules, server-authoritative expiry, command allowlist, media handling, and audit path.

## Fixed rule

The server remains the authority for session lifetime regardless of the launch method. A 15-minute session still expires 15 minutes after first successful activation. Switching launch methods must never extend or bypass the session expiry.

## Method A — Portable one-file EXE (primary)

Artifact: `RemoteSessionControl-Windows`

Purpose:

- Simplest direct launch on Windows.
- No Python installation.
- No project checkout.
- No virtual environment.
- Same screenshot, screen-recording, device-info, status, and disconnect commands.

Example after HTTPS/WSS deployment:

```powershell
.\RemoteSessionControl-Client.exe --server https://control.example.com
```

The client asks for the one-time pairing code and explicit local consent before activation.

## Method B — PowerShell launcher (fallback / convenience)

Script: `scripts/windows/Start-RemoteSession.ps1`

The launcher does not implement remote control itself. It only starts the same visible temporary client. It can either:

1. use an already-downloaded EXE via `-ClientPath`, or
2. download the EXE over HTTPS via `-ClientUrl`.

When `-ExpectedSha256` is supplied, the downloaded/client file is verified before execution.

Local-file example:

```powershell
.\Start-RemoteSession.ps1 `
  -Server https://control.example.com `
  -ClientPath .\RemoteSessionControl-Client.exe
```

Download-and-verify example:

```powershell
.\Start-RemoteSession.ps1 `
  -Server https://control.example.com `
  -ClientUrl https://control.example.com/downloads/RemoteSessionControl-Client.exe `
  -ExpectedSha256 <published-sha256>
```

The launcher uses `Start-Process`, so the launcher PowerShell window can be closed after the separate client starts. The client remains visible and still asks for local consent. No Windows service, Startup entry, registry autorun, scheduled task, or hidden persistence is installed.

For remote servers, the launcher rejects plain HTTP. Plain HTTP is accepted only for localhost testing.

## Method C — Portable runtime directory (fallback)

Artifact: `RemoteSessionControl-Windows-Portable`

This is a PyInstaller `--onedir` package. It contains the client and its bundled runtime/dependencies in a directory. It exists as a compatibility fallback for systems where the single-file executable has extraction or startup issues.

Usage:

```powershell
.\RemoteSessionControl-Portable\RemoteSessionControl-Portable.exe --server https://control.example.com
```

It requires no separately installed Python environment.

## Fallback order

Recommended order:

```text
Portable EXE
    ↓ if startup/runtime issue
PowerShell launcher
    ↓ if one-file packaging issue remains
Portable runtime directory
```

The user may choose any method directly. The fallback order is operational convenience only; it does not change privileges or session capabilities.

## Distribution design

Production distribution should publish:

- the Windows one-file client,
- its SHA-256 checksum,
- the PowerShell launcher,
- the Windows portable-runtime ZIP.

The server or a release channel may expose those files only after HTTPS is configured. Do not distribute secrets inside any client artifact. Pairing codes remain short-lived and session-specific.

## Security boundaries

All three methods retain the project security boundaries:

- explicit local execution and consent,
- no arbitrary shell command,
- no credential collection,
- no antivirus/EDR bypass,
- no hidden persistence,
- no automatic startup,
- no session-expiry bypass,
- capture only through the allowlisted session commands.

# Architecture Decision Records (condensed)

## ADR-001: Channel adapters

**Decision:** Keep Telegram/WhatsApp outside the core.  
**Reason:** Future channels should not force a rewrite.

## ADR-002: Activation-based session clock

**Decision:** `expires_at = first_successful_activation + requested_duration`.  
**Reason:** A user should not lose requested session time while preparing the remote device.

## ADR-003: Server-authoritative expiry

**Decision:** Client clocks cannot extend or restore sessions.  
**Reason:** Prevents local clock manipulation and divergent channel behavior.

## ADR-004: WebSocket control + HTTPS media

**Decision:** Persistent WSS for control; HTTPS multipart for larger media.  
**Reason:** Low-latency commands without sending large binary blobs through control frames.

## ADR-005: No arbitrary shell in MVP

**Decision:** Only explicit allowlisted commands.  
**Reason:** Smaller attack surface and clearer consent semantics.

## ADR-006: Stable non-secret instance ID

**Decision:** Store a random device identifier locally but keep session credentials in memory.  
**Reason:** Recognize devices across future sessions without creating a persistent authorization secret.

## ADR-007: Multiple Windows launch methods, one client/session model

**Decision:** Support one-file EXE, one-click BAT, one-click CMD compatibility, PowerShell, and portable-runtime ZIP as operationally interchangeable ways to start the same temporary Windows client.  
**Reason:** A packaging/startup issue in one method should not require a different protocol, security model, or server architecture. All methods use the same pairing code, Protocol v1, allowlisted commands, audit path, explicit consent, and server-authoritative expiry.

The BAT method is the preferred click-to-run path because it uses normal Windows command tools to download and SHA-256-verify the EXE and is not governed by PowerShell Execution Policy. The CMD compatibility path is a distinct fallback: it downloads and verifies the published PS1, then starts `powershell.exe -NoProfile -ExecutionPolicy Bypass -File ...` for that process only. It must not persistently change machine/user Execution Policy.

None of the launch methods may add hidden persistence, Startup entries, scheduled tasks, arbitrary shell access, or session-expiry bypasses.

## ADR-008: Lightweight Windows core + lazy recorder encoder

**Decision:** Keep FFmpeg out of the normal Windows one-file client and publish it as a separate SHA-256-verified helper that is fetched only when `RECORD_SCREEN` is first requested. NumPy, ImageIO, and Pillow are removed from the core capture path; MSS frames are piped directly to FFmpeg for H.264/MP4 encoding.  
**Reason:** Pairing, device info, screenshots, heartbeats, and disconnect do not need a video encoder. Carrying the encoder and numerical/image stacks in every initial client download made the development EXE unnecessarily large. The portable fallback may include the helper so that its recording path remains self-contained.

The build manifest contains the recorder-helper SHA-256 and is a public allowlisted non-secret artifact. Client/server secrets are never placed in the manifest or downloadable binaries.

## ADR-009: Signing is optional hardening

**Decision:** Code signing/notarization remains optional future hardening and is not required for the current temporary-session workflow.  
**Reason:** Current owner-operated development use can rely on HTTPS distribution, SHA-256 verification, visible local consent, and non-persistent launchers without introducing certificate subscription costs.

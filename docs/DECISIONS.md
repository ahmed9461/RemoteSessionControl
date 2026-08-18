# Architecture Decision Records (condensed)

## ADR-001: Channel adapters

**Decision:** Keep Telegram/WhatsApp outside the core.  
**Reason:** Future channels should not force a rewrite.

## ADR-002: Activation-based session clock

**Decision:** `expires_at = first_successful_activation + requested_duration`.  
**Reason:** A user should not lose purchased/requested session time while preparing the remote device.

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

**Decision:** Support a one-file EXE, a PowerShell launcher, and a portable-runtime ZIP as operationally interchangeable ways to start the same temporary Windows client.  
**Reason:** A packaging/startup issue in one method should not require a different protocol, security model, or server architecture. All methods use the same pairing code, Protocol v1, allowlisted commands, audit path, and server-authoritative expiry.

The PowerShell method may download the client only over HTTPS and verifies the published SHA-256 before starting it. None of the launch methods may add hidden persistence, Startup entries, scheduled tasks, arbitrary shell access, or session-expiry bypasses.

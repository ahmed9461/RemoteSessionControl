# Project Memory — Fixed Decisions

This file is authoritative project context for future developers and AI agents.

1. Telegram is an adapter, not the core.
2. WhatsApp is a future adapter and must reuse the same core.
3. Session duration starts at the first successful device activation, never at pairing-code creation.
4. Pairing-code expiry is independent from session duration.
5. The server is the sole authority for session expiry.
6. Reconnect never extends the session.
7. Device clients do not know which channel originated a command.
8. The device protocol is versioned from day one.
9. Media is temporary by default and automatically removed.
10. Commands are canonical and allowlisted.
11. The MVP contains no arbitrary shell execution.
12. The client is explicit-consent and visible; no stealth/persistence features are allowed in the core design.
13. Channel identities are independent records so Telegram can be enabled/disabled separately from future WhatsApp or web identities.
14. Architecture must remain extensible; adding a channel must not require a core rewrite.
15. Security-sensitive changes require tests and documentation updates.
16. Windows supports multiple operational launch methods for the same temporary client/session model: one-file EXE, one-click BAT, one-click CMD compatibility launcher, PowerShell launcher, and portable-runtime ZIP.
17. A fallback launch method must never change privileges, commands, pairing rules, local-consent rules, or session expiry.
18. Downloaded launchers/clients use HTTPS and SHA-256 verification before execution.
19. The BAT launcher is the preferred one-click Windows path because it does not depend on PowerShell Execution Policy.
20. The CMD compatibility launcher may invoke PowerShell with `-ExecutionPolicy Bypass` only for that child process; it must never change machine/user Execution Policy persistently.
21. Public client artifacts must never contain Telegram tokens, owner API keys, reconnect tokens, or other server secrets.
22. Production remote clients use HTTPS/WSS through a reverse proxy or equivalent secure ingress; Uvicorn remains bound to loopback.
23. The Windows core client is intentionally lightweight: NumPy, ImageIO, and Pillow are not part of its screen-capture path.
24. FFmpeg exists only to encode captured screen frames into H.264/MP4 for screen-recording commands; screenshots, device info, pairing, heartbeats, and disconnect do not require FFmpeg.
25. On Windows, FFmpeg is a separately published SHA-256-verified helper that is downloaded lazily only when screen recording is requested; the one-file client should not carry the encoder by default.
26. Portable Windows packaging may include the recorder helper for offline/fallback use while keeping the same command and session model.
27. Code signing is optional future hardening, not a current runtime requirement.

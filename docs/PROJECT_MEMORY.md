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

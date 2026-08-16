# Operator Runbook

## Startup order

1. Configure `.env`.
2. Start the FastAPI server.
3. Confirm `/health` returns `ok: true`.
4. Start the Telegram adapter.
5. Create a temporary session from Telegram.
6. Run the device client and enter the one-time pairing code.

## Production notes

- Terminate TLS at a trusted reverse proxy.
- Keep the server API key and Telegram token outside Git.
- Back up the database, not temporary media.
- Restrict inbound network ports to the reverse proxy entry point.
- Monitor service restarts and disk usage.

## Incident action

If a channel credential is exposed, rotate it and restart the affected adapter. If the owner API key is exposed, rotate it, invalidate all active sessions/reconnect tokens, and restart the server.

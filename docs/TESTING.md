# Testing

## Local

```bash
python -m compileall apps core channels infrastructure protocol tests
pytest -q
```

## Current automated coverage

- Session clock begins only at activation.
- Pairing code is single-use.
- Reconnect token is session-bound.
- Concurrent second session for the same device is rejected.
- Unknown commands are rejected.
- Screen-recording duration is bounded.
- Token hashing/randomness basics.

## Required future gates

Before a production release, add real integration tests for:

- WebSocket pair/reconnect lifecycle.
- Session expiry while connected and offline.
- Media TTL cleanup.
- Telegram command-to-result round trip.
- Windows screenshot and recording on a dedicated runner.
- macOS permission-denied behavior.
- PostgreSQL migrations.

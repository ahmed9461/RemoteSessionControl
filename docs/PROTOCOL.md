# Device Protocol v1

`protocol_version` is mandatory and currently equals `1`.

## Transport

- WebSocket over TLS (`wss://`) for control traffic in production.
- HTTPS multipart upload for screenshot/video media.
- Pairing and reconnect credentials are sent in the first WebSocket message, never in a URL query string.

## Pair hello

```json
{
  "protocol_version": 1,
  "type": "hello",
  "pairing_code": "ABCD-EFGH",
  "device": {
    "instance_id": "stable-non-secret-id",
    "name": "Laptop",
    "platform": "Windows",
    "platform_version": "...",
    "client_version": "0.1.0"
  }
}
```

## Reconnect hello

```json
{
  "protocol_version": 1,
  "type": "hello",
  "reconnect_token": "session-bound-secret",
  "device": {}
}
```

The reconnect token is valid only for the already-active session and never extends `expires_at`.

## Command

```json
{
  "protocol_version": 1,
  "type": "command",
  "command_id": "uuid",
  "command": "SCREENSHOT",
  "payload": {}
}
```

## Result

```json
{
  "protocol_version": 1,
  "type": "command_result",
  "command_id": "uuid",
  "success": true,
  "result": {},
  "media_id": "optional-uuid"
}
```

## Heartbeat

Client sends `heartbeat` approximately every 20 seconds. The server revalidates session authority before acknowledging it.

## Compatibility

Breaking message changes require Protocol v2. Protocol v1 semantics must not silently change in a way that makes old clients unsafe.

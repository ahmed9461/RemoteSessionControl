# Architecture

## Goal

RemoteSessionControl is a long-lived project in which messaging platforms are replaceable adapters. The core must remain independent of Telegram, WhatsApp, or any future UI.

## Layers

1. **Channels** — authenticate channel identities, translate UI/input into canonical commands, and return results to the origin.
2. **Core** — sessions, pairing, devices, command validation, identities, media metadata, expiry, and audit events.
3. **Protocol** — versioned messages shared by server and temporary device clients.
4. **Infrastructure** — database, WebSocket connection registry, storage, scheduling, logging.
5. **Device client** — executes only the allowlisted protocol commands while a server-authorized temporary session is active.

## Dependency rule

Dependencies point inward. Core code must never import Telegram or WhatsApp code. Device clients must never know which channel originated a request.

## Runtime topology

```text
Telegram adapter ---> HTTPS ---> FastAPI server <--- WSS ---> Device client
                                    |
                                    +--- SQLite (MVP) / PostgreSQL (future)
                                    +--- temporary media storage
```

## MVP processes

- `apps.server.app`: authoritative server.
- `apps.telegram.bot`: Telegram UI adapter.
- `apps.device_client.main`: explicit-consent Windows/macOS temporary client.

## Extension rule

Adding WhatsApp must require a new channel adapter and identity mapping only. It must not require changing the session state machine, device protocol, expiry semantics, or command meanings.

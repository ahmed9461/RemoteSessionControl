# Canonical Commands

The command router uses fixed command names independent of the originating messaging platform.

| Command | Payload | Result |
|---|---|---|
| `DEVICE_INFO` | `{}` | platform/device metadata |
| `SCREENSHOT` | `{}` | temporary image media |
| `RECORD_SCREEN` | `duration`, `fps` | temporary MP4 media |
| `SESSION_STATUS` | `{}` | server-side session state |
| `DISCONNECT` | `{}` | revokes session after client acknowledgment |

`RECORD_SCREEN` is restricted to 1–120 seconds and 2–10 FPS in protocol v1.

Unknown commands are rejected. Arbitrary command-shell execution is intentionally not part of the MVP.

# Session Model

## Fixed timing rule

Session duration starts at the **first successful device activation**.

```text
created_at != activated_at
expires_at = activated_at + requested_duration
```

Creating a pairing code does not start the session clock.

## States

```text
WAITING_FOR_DEVICE
        |
        | successful pairing
        v
      ACTIVE ------------------> REVOKED
        |
        | expires_at reached
        v
      EXPIRED
```

A waiting session whose pairing code expires is marked `FAILED` when used after expiry.

## Reconnect

A network interruption does not pause or extend time. The client may reconnect with its in-memory session token while `now < expires_at`.

If the session expires while offline, reconnect is rejected.

## Multiple devices

The database supports multiple devices. A stable non-secret instance identifier lets a device be recognized across separate pairings. One device cannot activate a second concurrent session in MVP.

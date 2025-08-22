# TCP File/Directory Transfer over TCP

Minimal Python implementation of a TCP server and client for transferring files and directories.

## Layout

- `tcp_transfer/common.py` — protocol and stream helpers
- `tcp_transfer/server.py` — threaded TCP server
- `tcp_transfer/client.py` — CLI client

## Requirements

- Python 3.9+

## Quick start

1. Start the server (in one terminal):

```bash
python -m tcp_transfer.server --host 0.0.0.0 --port 5050 --root /workspace/storage
```

2. Use the client (in another terminal):

```bash
# Ping
python -m tcp_transfer.client 127.0.0.1 5050 ping

# Upload a file
python -m tcp_transfer.client 127.0.0.1 5050 put-file /etc/hosts uploads/hosts.copy

# Download it back
python -m tcp_transfer.client 127.0.0.1 5050 get-file uploads/hosts.copy /workspace/downloads/hosts.copy

# Upload a directory
python -m tcp_transfer.client 127.0.0.1 5050 put-dir /usr/share/zoneinfo uploads/zoneinfo

# Download a directory
python -m tcp_transfer.client 127.0.0.1 5050 get-dir uploads/zoneinfo /workspace/downloads/zoneinfo
```

Notes:
- Paths given to the server are relative to the `--root` directory, with traversal prevented.
- Directory transfers stream entries with simple JSON headers (not tar). Permissions are preserved when provided.
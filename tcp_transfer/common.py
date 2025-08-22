import io
import json
import os
import socket
import struct
from typing import BinaryIO, Dict, Optional, Tuple

# Protocol:
# - Each message begins with a 4-byte big-endian unsigned length N of the header.
# - Followed by N bytes of UTF-8 JSON header. The header MUST include a "type" field.
# - Optional binary payload follows; its size is specified by header["content_length"].
# - For directory transfers, we stream a tar-like sequence of entries with per-entry headers.

HEADER_LEN_STRUCT = struct.Struct(">I")


def _recvall(sock: socket.socket, nbytes: int) -> bytes:
	buf = bytearray()
	while len(buf) < nbytes:
		chunk = sock.recv(nbytes - len(buf))
		if not chunk:
			raise ConnectionError("socket closed during recv")
		buf.extend(chunk)
	return bytes(buf)


def send_header(sock: socket.socket, header: Dict) -> None:
	data = json.dumps(header, separators=(",", ":")).encode("utf-8")
	if len(data) > (2 ** 31):
		raise ValueError("header too large")
	sock.sendall(HEADER_LEN_STRUCT.pack(len(data)))
	sock.sendall(data)


def recv_header(sock: socket.socket) -> Dict:
	(hlen,) = HEADER_LEN_STRUCT.unpack(_recvall(sock, HEADER_LEN_STRUCT.size))
	data = _recvall(sock, hlen)
	return json.loads(data.decode("utf-8"))


def send_stream(sock: socket.socket, stream: BinaryIO, total_bytes: int, chunk_size: int = 65536) -> None:
	remaining = total_bytes
	while remaining > 0:
		chunk = stream.read(min(chunk_size, remaining))
		if not chunk:
			raise IOError("unexpected EOF in stream during send")
		sock.sendall(chunk)
		remaining -= len(chunk)


def recv_to_stream(sock: socket.socket, out: BinaryIO, total_bytes: int, chunk_size: int = 65536) -> None:
	remaining = total_bytes
	while remaining > 0:
		chunk = sock.recv(min(chunk_size, remaining))
		if not chunk:
			raise ConnectionError("socket closed during payload recv")
		out.write(chunk)
		remaining -= len(chunk)


# Basic file utilities

def ensure_parent_dir(path: str) -> None:
	dirname = os.path.dirname(path)
	if dirname and not os.path.exists(dirname):
		os.makedirs(dirname, exist_ok=True)


def stat_path(path: str) -> Dict:
	st = os.stat(path)
	return {
		"size": st.st_size,
		"mtime": st.st_mtime,
		"mode": st.st_mode,
	}


# Directory streaming (simple tar-like framing)
ENTRY_HEADER = struct.Struct(">I")


def iter_directory_entries(root_dir: str):
	root_dir = os.path.abspath(root_dir)
	for base, dirs, files in os.walk(root_dir):
		rel_base = os.path.relpath(base, root_dir)
		if rel_base == ".":
			rel_base = ""
		for d in dirs:
			yield {
				"type": "dir",
				"path": os.path.join(rel_base, d),
			}
		for f in files:
			full = os.path.join(base, f)
			st = os.stat(full)
			yield {
				"type": "file",
				"path": os.path.join(rel_base, f),
				"size": st.st_size,
				"mode": st.st_mode,
				"mtime": st.st_mtime,
			}


def send_directory(sock: socket.socket, root_dir: str) -> None:
	# Send entries until a terminal empty header {}
	for entry in iter_directory_entries(root_dir):
		send_header(sock, entry)
		if entry["type"] == "file":
			with open(os.path.join(root_dir, entry["path"]), "rb") as f:
				send_stream(sock, f, entry["size"]) 
	# end marker
	send_header(sock, {"type": "end"})


def recv_directory(sock: socket.socket, dest_dir: str) -> None:
	while True:
		h = recv_header(sock)
		t = h.get("type")
		if t == "end":
			break
		if t == "dir":
			os.makedirs(os.path.join(dest_dir, h["path"]), exist_ok=True)
		elif t == "file":
			out_path = os.path.join(dest_dir, h["path"])
			ensure_parent_dir(out_path)
			with open(out_path, "wb") as out:
				recv_to_stream(sock, out, int(h["size"]))
			if "mode" in h:
				os.chmod(out_path, int(h["mode"]))
		else:
			raise ValueError(f"unknown entry type: {t}")
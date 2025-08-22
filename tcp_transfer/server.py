import os
import socket
import threading
from typing import Dict

from .common import (
	recv_header,
	recv_to_stream,
	send_header,
	send_stream,
	send_directory,
	recv_directory,
	ensure_parent_dir,
)


class FileServer:
	def __init__(self, root_dir: str) -> None:
		self.root_dir = os.path.abspath(root_dir)
		os.makedirs(self.root_dir, exist_ok=True)

	def _abs_path(self, rel_path: str) -> str:
		unsafe = os.path.abspath(os.path.join(self.root_dir, rel_path))
		if not unsafe.startswith(self.root_dir + os.sep) and unsafe != self.root_dir:
			raise PermissionError("path traversal detected")
		return unsafe

	def handle_client(self, conn: socket.socket, addr) -> None:
		try:
			while True:
				req = recv_header(conn)
				type_ = req.get("type")
				if type_ == "ping":
					send_header(conn, {"type": "pong"})
				elif type_ == "put_file":
					self._handle_put_file(conn, req)
				elif type_ == "get_file":
					self._handle_get_file(conn, req)
				elif type_ == "put_dir":
					self._handle_put_dir(conn, req)
				elif type_ == "get_dir":
					self._handle_get_dir(conn, req)
				elif type_ == "bye":
					send_header(conn, {"type": "bye"})
					break
				else:
					send_header(conn, {"type": "error", "message": f"unknown request: {type_}"})
		except Exception as e:
			try:
				send_header(conn, {"type": "error", "message": str(e)})
			except Exception:
				pass
		finally:
			try:
				conn.close()
			except Exception:
				pass

	def _handle_put_file(self, conn: socket.socket, req: Dict) -> None:
		rel_path = req["path"]
		size = int(req["size"])
		abs_path = self._abs_path(rel_path)
		ensure_parent_dir(abs_path)
		with open(abs_path, "wb") as out:
			recv_to_stream(conn, out, size)
		send_header(conn, {"type": "ok"})

	def _handle_get_file(self, conn: socket.socket, req: Dict) -> None:
		abs_path = self._abs_path(req["path"])
		st = os.stat(abs_path)
		send_header(conn, {"type": "file_info", "size": st.st_size})
		with open(abs_path, "rb") as f:
			send_stream(conn, f, st.st_size)

	def _handle_put_dir(self, conn: socket.socket, req: Dict) -> None:
		rel_path = req.get("path", ".")
		dest = self._abs_path(rel_path)
		os.makedirs(dest, exist_ok=True)
		recv_directory(conn, dest)
		send_header(conn, {"type": "ok"})

	def _handle_get_dir(self, conn: socket.socket, req: Dict) -> None:
		src = self._abs_path(req.get("path", "."))
		send_directory(conn, src)


def serve(host: str, port: int, root_dir: str) -> None:
	server = FileServer(root_dir)
	sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
	sock.bind((host, port))
	sock.listen()
	print(f"Server listening on {host}:{port}, root={root_dir}")
	try:
		while True:
			conn, addr = sock.accept()
			threading.Thread(target=server.handle_client, args=(conn, addr), daemon=True).start()
	finally:
		sock.close()


if __name__ == "__main__":
	import argparse
	parser = argparse.ArgumentParser(description="TCP File Server")
	parser.add_argument("--host", default="0.0.0.0")
	parser.add_argument("--port", type=int, default=5050)
	parser.add_argument("--root", default="/workspace/storage")
	args = parser.parse_args()
	serve(args.host, args.port, args.root)
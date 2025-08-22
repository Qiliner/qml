import os
import socket
from typing import Optional

from .common import (
	send_header,
	recv_header,
	recv_to_stream,
	send_stream,
	send_directory,
	recv_directory,
	ensure_parent_dir,
)


class Client:
	def __init__(self, host: str, port: int) -> None:
		self.host = host
		self.port = port

	def _connect(self) -> socket.socket:
		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		sock.connect((self.host, self.port))
		return sock

	def ping(self) -> bool:
		sock = self._connect()
		try:
			send_header(sock, {"type": "ping"})
			resp = recv_header(sock)
			return resp.get("type") == "pong"
		finally:
			sock.close()

	def put_file(self, local_path: str, remote_path: str) -> None:
		st = os.stat(local_path)
		sock = self._connect()
		try:
			send_header(sock, {"type": "put_file", "path": remote_path, "size": st.st_size})
			with open(local_path, "rb") as f:
				send_stream(sock, f, st.st_size)
			resp = recv_header(sock)
			if resp.get("type") != "ok":
				raise RuntimeError(resp)
		finally:
			sock.close()

	def get_file(self, remote_path: str, local_path: str) -> None:
		sock = self._connect()
		try:
			send_header(sock, {"type": "get_file", "path": remote_path})
			info = recv_header(sock)
			if info.get("type") != "file_info":
				raise RuntimeError(info)
			ensure_parent_dir(local_path)
			with open(local_path, "wb") as out:
				recv_to_stream(sock, out, int(info["size"]))
		finally:
			sock.close()

	def put_dir(self, local_dir: str, remote_dir: str) -> None:
		sock = self._connect()
		try:
			send_header(sock, {"type": "put_dir", "path": remote_dir})
			send_directory(sock, local_dir)
			resp = recv_header(sock)
			if resp.get("type") != "ok":
				raise RuntimeError(resp)
		finally:
			sock.close()

	def get_dir(self, remote_dir: str, local_dir: str) -> None:
		sock = self._connect()
		try:
			send_header(sock, {"type": "get_dir", "path": remote_dir})
			recv_directory(sock, local_dir)
		finally:
			sock.close()


if __name__ == "__main__":
	import argparse
	parser = argparse.ArgumentParser(description="TCP file client")
	parser.add_argument("host")
	parser.add_argument("port", type=int)
	sub = parser.add_subparsers(dest="cmd", required=True)
	sp = sub.add_parser("ping")
	spf = sub.add_parser("put-file")
	spf.add_argument("local")
	spf.add_argument("remote")
	sgf = sub.add_parser("get-file")
	sgf.add_argument("remote")
	sgf.add_argument("local")
	spd = sub.add_parser("put-dir")
	spd.add_argument("local")
	spd.add_argument("remote")
	sgd = sub.add_parser("get-dir")
	sgd.add_argument("remote")
	sgd.add_argument("local")
	args = parser.parse_args()

	cli = Client(args.host, args.port)
	if args.cmd == "ping":
		ok = cli.ping()
		print("pong" if ok else "no pong")
	elif args.cmd == "put-file":
		cli.put_file(args.local, args.remote)
		print("uploaded")
	elif args.cmd == "get-file":
		cli.get_file(args.remote, args.local)
		print("downloaded")
	elif args.cmd == "put-dir":
		cli.put_dir(args.local, args.remote)
		print("dir uploaded")
	elif args.cmd == "get-dir":
		cli.get_dir(args.remote, args.local)
		print("dir downloaded")
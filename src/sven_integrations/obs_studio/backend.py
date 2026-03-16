"""OBS Studio WebSocket backend — communicates via obs-websocket protocol."""

from __future__ import annotations

import base64
import hashlib
import json
import socket
import threading
import time
import uuid
from typing import Any


class ObsConnectionError(RuntimeError):
    """Raised when the OBS WebSocket connection cannot be established."""


class ObsRequestError(RuntimeError):
    """Raised when OBS returns an error response to a request."""


class ObsBackend:
    """Controls OBS Studio via the obs-websocket JSON-RPC protocol.

    Uses stdlib ``socket`` for the raw TCP/WebSocket handshake, avoiding
    any third-party WebSocket dependency.  The implementation handles the
    obs-websocket v5 protocol (used by OBS 28+).
    """

    _WS_MAGIC = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
    _OPCODE_TEXT = 0x81
    _OPCODE_CLOSE = 0x88

    def __init__(self) -> None:
        self._sock: socket.socket | None = None
        self._host = "localhost"
        self._port = 4455
        self._lock = threading.Lock()
        self._connected = False

    # ------------------------------------------------------------------
    # Connection lifecycle

    def connect(
        self,
        host: str = "localhost",
        port: int = 4455,
        password: str = "",
    ) -> None:
        """Open a WebSocket connection to OBS and perform authentication."""
        self._host = host
        self._port = port
        try:
            self._sock = socket.create_connection((host, port), timeout=10)
        except OSError as exc:
            raise ObsConnectionError(
                f"Cannot connect to OBS WebSocket at {host}:{port}: {exc}"
            ) from exc

        self._ws_handshake(host, port)

        hello = self._recv_message()
        if hello.get("op") != 0:
            raise ObsConnectionError(f"Expected Hello (op=0), got: {hello}")

        auth_required = hello.get("d", {}).get("authentication")
        identify_data: dict[str, Any] = {"rpcVersion": 1}
        if auth_required and password:
            identify_data["authentication"] = self._compute_auth(
                password,
                auth_required["challenge"],
                auth_required["salt"],
            )
        self._send_message({"op": 1, "d": identify_data})

        identified = self._recv_message()
        if identified.get("op") != 2:
            raise ObsConnectionError(f"Authentication failed: {identified}")

        self._connected = True

    def disconnect(self) -> None:
        """Close the WebSocket connection."""
        if self._sock is not None:
            try:
                self._send_raw(bytes([self._OPCODE_CLOSE, 0]))
                self._sock.close()
            except OSError:
                pass
            self._sock = None
        self._connected = False

    def is_connected(self) -> bool:
        return self._connected and self._sock is not None

    # ------------------------------------------------------------------
    # Request dispatch

    def call(self, request_type: str, data: dict[str, Any] | None = None) -> dict[str, Any]:
        """Send a request to OBS and return the response data dict.

        Raises ``ObsRequestError`` if OBS reports a non-success status.
        """
        if not self.is_connected():
            raise ObsConnectionError("Not connected — call connect() first.")

        request_id = str(uuid.uuid4())
        payload: dict[str, Any] = {
            "op": 6,
            "d": {
                "requestType": request_type,
                "requestId": request_id,
                "requestData": data or {},
            },
        }
        with self._lock:
            self._send_message(payload)
            response = self._recv_message()

        if response.get("op") != 7:
            raise ObsRequestError(f"Unexpected response opcode: {response.get('op')}")

        resp_data = response.get("d", {})
        status = resp_data.get("requestStatus", {})
        if not status.get("result", False):
            code = status.get("code", -1)
            comment = status.get("comment", "")
            raise ObsRequestError(
                f"OBS request {request_type!r} failed (code={code}): {comment}"
            )

        return resp_data.get("responseData", {})

    def get_version(self) -> str:
        """Return the OBS Studio version string."""
        data = self.call("GetVersion")
        return data.get("obsVersion", "unknown")

    # ------------------------------------------------------------------
    # Context manager

    def __enter__(self) -> "ObsBackend":
        return self

    def __exit__(self, *_: object) -> None:
        self.disconnect()

    # ------------------------------------------------------------------
    # Low-level WebSocket helpers

    def _ws_handshake(self, host: str, port: int) -> None:
        key = base64.b64encode(uuid.uuid4().bytes).decode()
        request = (
            f"GET / HTTP/1.1\r\n"
            f"Host: {host}:{port}\r\n"
            f"Upgrade: websocket\r\n"
            f"Connection: Upgrade\r\n"
            f"Sec-WebSocket-Key: {key}\r\n"
            f"Sec-WebSocket-Version: 13\r\n"
            f"\r\n"
        )
        assert self._sock is not None
        self._sock.sendall(request.encode())
        resp = b""
        while b"\r\n\r\n" not in resp:
            chunk = self._sock.recv(4096)
            if not chunk:
                raise ObsConnectionError("Connection closed during WebSocket handshake")
            resp += chunk

    def _send_raw(self, data: bytes) -> None:
        assert self._sock is not None
        self._sock.sendall(data)

    def _send_message(self, payload: dict[str, Any]) -> None:
        text = json.dumps(payload)
        data = text.encode("utf-8")
        length = len(data)
        header = bytearray()
        header.append(self._OPCODE_TEXT)
        if length <= 125:
            header.append(length)
        elif length <= 65535:
            header.append(126)
            header += length.to_bytes(2, "big")
        else:
            header.append(127)
            header += length.to_bytes(8, "big")
        self._send_raw(bytes(header) + data)

    def _recv_message(self) -> dict[str, Any]:
        assert self._sock is not None
        header = self._recv_exact(2)
        opcode = header[0] & 0x0F
        payload_len = header[1] & 0x7F
        if payload_len == 126:
            payload_len = int.from_bytes(self._recv_exact(2), "big")
        elif payload_len == 127:
            payload_len = int.from_bytes(self._recv_exact(8), "big")
        body = self._recv_exact(payload_len)
        return json.loads(body.decode("utf-8"))

    def _recv_exact(self, n: int) -> bytes:
        assert self._sock is not None
        buf = b""
        while len(buf) < n:
            chunk = self._sock.recv(n - len(buf))
            if not chunk:
                raise ObsConnectionError("Connection closed unexpectedly")
            buf += chunk
        return buf

    @staticmethod
    def _compute_auth(password: str, challenge: str, salt: str) -> str:
        secret = base64.b64encode(
            hashlib.sha256((password + salt).encode()).digest()
        ).decode()
        auth = base64.b64encode(
            hashlib.sha256((secret + challenge).encode()).digest()
        ).decode()
        return auth

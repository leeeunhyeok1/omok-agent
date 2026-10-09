# AI-written by OpenAI Codex, for issue #25.
"""Length-bounded JSON frames on a private loopback worker connection."""
import json
import socket
import struct
from time import monotonic
from typing import Any

MAX_FRAME = 65536


class ProtocolError(Exception):
    pass


def send(connection: socket.socket, value: dict[str, Any], deadline: float) -> None:
    data = json.dumps(value, allow_nan=False).encode('utf-8')
    if len(data) > MAX_FRAME:
        raise ProtocolError('Worker frame exceeds limit.')
    connection.settimeout(max(0.000001, deadline - monotonic()))
    connection.sendall(struct.pack('!I', len(data)) + data)


def receive(connection: socket.socket, deadline: float) -> dict[str, Any]:
    def read(count: int) -> bytes:
        data = bytearray()
        while len(data) < count:
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise TimeoutError('Worker deadline expired.')
            connection.settimeout(remaining)
            chunk = connection.recv(count - len(data))
            if not chunk:
                raise EOFError('Worker connection closed.')
            data.extend(chunk)
        return bytes(data)
    size = struct.unpack('!I', read(4))[0]
    if size > MAX_FRAME:
        raise ProtocolError('Worker frame exceeds limit.')
    try:
        value = json.loads(read(size), parse_constant=lambda s: (_ for _ in ()).throw(ValueError(s)))
    except (ValueError, UnicodeError) as error:
        raise ProtocolError('Malformed worker JSON.') from error
    if not isinstance(value, dict):
        raise ProtocolError('Worker frame must be an object.')
    return value

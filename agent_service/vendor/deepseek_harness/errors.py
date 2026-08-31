from __future__ import annotations


"""固定 DSH SDK对外错误类型。"""

class HarnessError(Exception):
    """Base exception for SDK and runtime failures."""


class TransportClosedError(HarnessError):
    """Raised when the runtime subprocess exits or closes stdout."""


class SdkProtocolError(HarnessError):
    """Raised when the runtime sends data outside the SDK protocol."""


class JsonRpcError(HarnessError):
    """Raised when the runtime returns a JSON-RPC error response."""

    def __init__(self, code: int | None, message: str, data: object | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data

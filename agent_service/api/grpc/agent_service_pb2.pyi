from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class RunRequest(_message.Message):
    __slots__ = ("prompt", "user_id", "session_id")
    PROMPT_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    prompt: str
    user_id: str
    session_id: str
    def __init__(self, prompt: _Optional[str] = ..., user_id: _Optional[str] = ..., session_id: _Optional[str] = ...) -> None: ...

class RunResult(_message.Message):
    __slots__ = ("graph_diagram", "final_output", "events_json", "chunks_json")
    GRAPH_DIAGRAM_FIELD_NUMBER: _ClassVar[int]
    FINAL_OUTPUT_FIELD_NUMBER: _ClassVar[int]
    EVENTS_JSON_FIELD_NUMBER: _ClassVar[int]
    CHUNKS_JSON_FIELD_NUMBER: _ClassVar[int]
    graph_diagram: str
    final_output: str
    events_json: str
    chunks_json: str
    def __init__(self, graph_diagram: _Optional[str] = ..., final_output: _Optional[str] = ..., events_json: _Optional[str] = ..., chunks_json: _Optional[str] = ...) -> None: ...

class ToolCall(_message.Message):
    __slots__ = ("name", "args_json", "id")
    NAME_FIELD_NUMBER: _ClassVar[int]
    ARGS_JSON_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    name: str
    args_json: str
    id: str
    def __init__(self, name: _Optional[str] = ..., args_json: _Optional[str] = ..., id: _Optional[str] = ...) -> None: ...

class TraceEntry(_message.Message):
    __slots__ = ("node", "event", "error_type", "message")
    NODE_FIELD_NUMBER: _ClassVar[int]
    EVENT_FIELD_NUMBER: _ClassVar[int]
    ERROR_TYPE_FIELD_NUMBER: _ClassVar[int]
    MESSAGE_FIELD_NUMBER: _ClassVar[int]
    node: str
    event: str
    error_type: str
    message: str
    def __init__(self, node: _Optional[str] = ..., event: _Optional[str] = ..., error_type: _Optional[str] = ..., message: _Optional[str] = ...) -> None: ...

class ChunkMessage(_message.Message):
    __slots__ = ("node", "content", "tool_calls", "trace", "done")
    NODE_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    TOOL_CALLS_FIELD_NUMBER: _ClassVar[int]
    TRACE_FIELD_NUMBER: _ClassVar[int]
    DONE_FIELD_NUMBER: _ClassVar[int]
    node: str
    content: str
    tool_calls: _containers.RepeatedCompositeFieldContainer[ToolCall]
    trace: _containers.RepeatedCompositeFieldContainer[TraceEntry]
    done: bool
    def __init__(self, node: _Optional[str] = ..., content: _Optional[str] = ..., tool_calls: _Optional[_Iterable[_Union[ToolCall, _Mapping]]] = ..., trace: _Optional[_Iterable[_Union[TraceEntry, _Mapping]]] = ..., done: bool = ...) -> None: ...

class SessionCreateRequest(_message.Message):
    __slots__ = ("user_id", "session_name")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    SESSION_NAME_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    session_name: str
    def __init__(self, user_id: _Optional[str] = ..., session_name: _Optional[str] = ...) -> None: ...

class SessionIdRequest(_message.Message):
    __slots__ = ("session_id",)
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    def __init__(self, session_id: _Optional[str] = ...) -> None: ...

class ListSessionsRequest(_message.Message):
    __slots__ = ("user_id",)
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    def __init__(self, user_id: _Optional[str] = ...) -> None: ...

class SessionUpdateRequest(_message.Message):
    __slots__ = ("session_id", "session_name")
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    SESSION_NAME_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    session_name: str
    def __init__(self, session_id: _Optional[str] = ..., session_name: _Optional[str] = ...) -> None: ...

class SessionResponse(_message.Message):
    __slots__ = ("session_id", "user_id", "session_name", "created_at", "updated_at")
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    SESSION_NAME_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    user_id: str
    session_name: str
    created_at: str
    updated_at: str
    def __init__(self, session_id: _Optional[str] = ..., user_id: _Optional[str] = ..., session_name: _Optional[str] = ..., created_at: _Optional[str] = ..., updated_at: _Optional[str] = ...) -> None: ...

class ListSessionsResponse(_message.Message):
    __slots__ = ("sessions",)
    SESSIONS_FIELD_NUMBER: _ClassVar[int]
    sessions: _containers.RepeatedCompositeFieldContainer[SessionResponse]
    def __init__(self, sessions: _Optional[_Iterable[_Union[SessionResponse, _Mapping]]] = ...) -> None: ...

class DeleteResponse(_message.Message):
    __slots__ = ("success",)
    SUCCESS_FIELD_NUMBER: _ClassVar[int]
    success: bool
    def __init__(self, success: bool = ...) -> None: ...

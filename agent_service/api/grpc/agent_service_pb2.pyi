from google.protobuf import struct_pb2 as _struct_pb2
from google.protobuf.internal import containers as _containers
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from typing import ClassVar as _ClassVar, Iterable as _Iterable, Mapping as _Mapping, Optional as _Optional, Union as _Union

DESCRIPTOR: _descriptor.FileDescriptor

class RunRequest(_message.Message):
    __slots__ = ("prompt", "user_id", "session_id", "reference")
    PROMPT_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    REFERENCE_FIELD_NUMBER: _ClassVar[int]
    prompt: str
    user_id: str
    session_id: str
    reference: str
    def __init__(self, prompt: _Optional[str] = ..., user_id: _Optional[str] = ..., session_id: _Optional[str] = ..., reference: _Optional[str] = ...) -> None: ...

class RunResult(_message.Message):
    __slots__ = ("graph_diagram", "final_output", "events", "graph_diagram_path")
    GRAPH_DIAGRAM_FIELD_NUMBER: _ClassVar[int]
    FINAL_OUTPUT_FIELD_NUMBER: _ClassVar[int]
    EVENTS_FIELD_NUMBER: _ClassVar[int]
    GRAPH_DIAGRAM_PATH_FIELD_NUMBER: _ClassVar[int]
    graph_diagram: str
    final_output: str
    events: _containers.RepeatedCompositeFieldContainer[_struct_pb2.Struct]
    graph_diagram_path: str
    def __init__(self, graph_diagram: _Optional[str] = ..., final_output: _Optional[str] = ..., events: _Optional[_Iterable[_Union[_struct_pb2.Struct, _Mapping]]] = ..., graph_diagram_path: _Optional[str] = ...) -> None: ...

class ToolCall(_message.Message):
    __slots__ = ("name", "args", "id")
    NAME_FIELD_NUMBER: _ClassVar[int]
    ARGS_FIELD_NUMBER: _ClassVar[int]
    ID_FIELD_NUMBER: _ClassVar[int]
    name: str
    args: _struct_pb2.Struct
    id: str
    def __init__(self, name: _Optional[str] = ..., args: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., id: _Optional[str] = ...) -> None: ...

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
    __slots__ = ("node", "content", "tool_calls", "trace", "done", "model_name", "type", "context_messages", "metadata", "error")
    NODE_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    TOOL_CALLS_FIELD_NUMBER: _ClassVar[int]
    TRACE_FIELD_NUMBER: _ClassVar[int]
    DONE_FIELD_NUMBER: _ClassVar[int]
    MODEL_NAME_FIELD_NUMBER: _ClassVar[int]
    TYPE_FIELD_NUMBER: _ClassVar[int]
    CONTEXT_MESSAGES_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    ERROR_FIELD_NUMBER: _ClassVar[int]
    node: str
    content: str
    tool_calls: _containers.RepeatedCompositeFieldContainer[ToolCall]
    trace: _containers.RepeatedCompositeFieldContainer[TraceEntry]
    done: bool
    model_name: str
    type: str
    context_messages: _containers.RepeatedCompositeFieldContainer[_struct_pb2.Struct]
    metadata: _struct_pb2.Struct
    error: str
    def __init__(self, node: _Optional[str] = ..., content: _Optional[str] = ..., tool_calls: _Optional[_Iterable[_Union[ToolCall, _Mapping]]] = ..., trace: _Optional[_Iterable[_Union[TraceEntry, _Mapping]]] = ..., done: bool = ..., model_name: _Optional[str] = ..., type: _Optional[str] = ..., context_messages: _Optional[_Iterable[_Union[_struct_pb2.Struct, _Mapping]]] = ..., metadata: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., error: _Optional[str] = ...) -> None: ...

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
    __slots__ = ("ok", "deleted_count")
    OK_FIELD_NUMBER: _ClassVar[int]
    DELETED_COUNT_FIELD_NUMBER: _ClassVar[int]
    ok: bool
    deleted_count: int
    def __init__(self, ok: bool = ..., deleted_count: _Optional[int] = ...) -> None: ...

class DeleteAllSessionsRequest(_message.Message):
    __slots__ = ("user_id",)
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    def __init__(self, user_id: _Optional[str] = ...) -> None: ...

class ListMessagesRequest(_message.Message):
    __slots__ = ("user_id", "session_id", "limit")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    LIMIT_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    session_id: str
    limit: int
    def __init__(self, user_id: _Optional[str] = ..., session_id: _Optional[str] = ..., limit: _Optional[int] = ...) -> None: ...

class MessageEntry(_message.Message):
    __slots__ = ("message_id", "session_id", "user_id", "role", "content", "tool_calls", "metadata", "created_at")
    MESSAGE_ID_FIELD_NUMBER: _ClassVar[int]
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    ROLE_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    TOOL_CALLS_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    message_id: str
    session_id: str
    user_id: str
    role: str
    content: str
    tool_calls: _containers.RepeatedCompositeFieldContainer[ToolCall]
    metadata: _struct_pb2.Struct
    created_at: str
    def __init__(self, message_id: _Optional[str] = ..., session_id: _Optional[str] = ..., user_id: _Optional[str] = ..., role: _Optional[str] = ..., content: _Optional[str] = ..., tool_calls: _Optional[_Iterable[_Union[ToolCall, _Mapping]]] = ..., metadata: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., created_at: _Optional[str] = ...) -> None: ...

class ListMessagesResponse(_message.Message):
    __slots__ = ("messages",)
    MESSAGES_FIELD_NUMBER: _ClassVar[int]
    messages: _containers.RepeatedCompositeFieldContainer[MessageEntry]
    def __init__(self, messages: _Optional[_Iterable[_Union[MessageEntry, _Mapping]]] = ...) -> None: ...

class EventsRequest(_message.Message):
    __slots__ = ("user_id", "session_id")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    session_id: str
    def __init__(self, user_id: _Optional[str] = ..., session_id: _Optional[str] = ...) -> None: ...

class EventEntry(_message.Message):
    __slots__ = ("message_id", "role", "node", "content", "tool_calls", "created_at", "metadata")
    MESSAGE_ID_FIELD_NUMBER: _ClassVar[int]
    ROLE_FIELD_NUMBER: _ClassVar[int]
    NODE_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    TOOL_CALLS_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    METADATA_FIELD_NUMBER: _ClassVar[int]
    message_id: str
    role: str
    node: str
    content: str
    tool_calls: _containers.RepeatedCompositeFieldContainer[ToolCall]
    created_at: str
    metadata: _struct_pb2.Struct
    def __init__(self, message_id: _Optional[str] = ..., role: _Optional[str] = ..., node: _Optional[str] = ..., content: _Optional[str] = ..., tool_calls: _Optional[_Iterable[_Union[ToolCall, _Mapping]]] = ..., created_at: _Optional[str] = ..., metadata: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ...) -> None: ...

class EventsResponse(_message.Message):
    __slots__ = ("session_id", "user_id", "event_count", "events")
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    EVENT_COUNT_FIELD_NUMBER: _ClassVar[int]
    EVENTS_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    user_id: str
    event_count: int
    events: _containers.RepeatedCompositeFieldContainer[EventEntry]
    def __init__(self, session_id: _Optional[str] = ..., user_id: _Optional[str] = ..., event_count: _Optional[int] = ..., events: _Optional[_Iterable[_Union[EventEntry, _Mapping]]] = ...) -> None: ...

class RecallDetailsRequest(_message.Message):
    __slots__ = ("user_id", "session_id")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    session_id: str
    def __init__(self, user_id: _Optional[str] = ..., session_id: _Optional[str] = ...) -> None: ...

class RecallDetailsResponse(_message.Message):
    __slots__ = ("session_id", "user_id", "created_at", "query", "rag_metrics", "memory_recall", "knowledge_recall")
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    QUERY_FIELD_NUMBER: _ClassVar[int]
    RAG_METRICS_FIELD_NUMBER: _ClassVar[int]
    MEMORY_RECALL_FIELD_NUMBER: _ClassVar[int]
    KNOWLEDGE_RECALL_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    user_id: str
    created_at: str
    query: str
    rag_metrics: _struct_pb2.Struct
    memory_recall: _struct_pb2.Struct
    knowledge_recall: _struct_pb2.Struct
    def __init__(self, session_id: _Optional[str] = ..., user_id: _Optional[str] = ..., created_at: _Optional[str] = ..., query: _Optional[str] = ..., rag_metrics: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., memory_recall: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., knowledge_recall: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ...) -> None: ...

class ToolListRequest(_message.Message):
    __slots__ = ()
    def __init__(self) -> None: ...

class ToolInfo(_message.Message):
    __slots__ = ("name", "display_name", "description", "args_schema", "argument_count")
    NAME_FIELD_NUMBER: _ClassVar[int]
    DISPLAY_NAME_FIELD_NUMBER: _ClassVar[int]
    DESCRIPTION_FIELD_NUMBER: _ClassVar[int]
    ARGS_SCHEMA_FIELD_NUMBER: _ClassVar[int]
    ARGUMENT_COUNT_FIELD_NUMBER: _ClassVar[int]
    name: str
    display_name: str
    description: str
    args_schema: _struct_pb2.Struct
    argument_count: int
    def __init__(self, name: _Optional[str] = ..., display_name: _Optional[str] = ..., description: _Optional[str] = ..., args_schema: _Optional[_Union[_struct_pb2.Struct, _Mapping]] = ..., argument_count: _Optional[int] = ...) -> None: ...

class ToolListResponse(_message.Message):
    __slots__ = ("tool_count", "tools")
    TOOL_COUNT_FIELD_NUMBER: _ClassVar[int]
    TOOLS_FIELD_NUMBER: _ClassVar[int]
    tool_count: int
    tools: _containers.RepeatedCompositeFieldContainer[ToolInfo]
    def __init__(self, tool_count: _Optional[int] = ..., tools: _Optional[_Iterable[_Union[ToolInfo, _Mapping]]] = ...) -> None: ...

class CancelRequest(_message.Message):
    __slots__ = ("session_id",)
    SESSION_ID_FIELD_NUMBER: _ClassVar[int]
    session_id: str
    def __init__(self, session_id: _Optional[str] = ...) -> None: ...

class CancelResponse(_message.Message):
    __slots__ = ("ok",)
    OK_FIELD_NUMBER: _ClassVar[int]
    ok: bool
    def __init__(self, ok: bool = ...) -> None: ...

class UserProfileRequest(_message.Message):
    __slots__ = ("user_id",)
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    def __init__(self, user_id: _Optional[str] = ...) -> None: ...

class UserKnowledgeDirUpdateRequest(_message.Message):
    __slots__ = ("user_id", "knowledge_dir", "name")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    KNOWLEDGE_DIR_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    knowledge_dir: str
    name: str
    def __init__(self, user_id: _Optional[str] = ..., knowledge_dir: _Optional[str] = ..., name: _Optional[str] = ...) -> None: ...

class UserProfileResponse(_message.Message):
    __slots__ = ("user_id", "knowledge_dir", "created_at", "updated_at", "active_library_id", "active_knowledge_library", "knowledge_libraries")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    KNOWLEDGE_DIR_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    ACTIVE_LIBRARY_ID_FIELD_NUMBER: _ClassVar[int]
    ACTIVE_KNOWLEDGE_LIBRARY_FIELD_NUMBER: _ClassVar[int]
    KNOWLEDGE_LIBRARIES_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    knowledge_dir: str
    created_at: str
    updated_at: str
    active_library_id: str
    active_knowledge_library: KnowledgeLibraryEntry
    knowledge_libraries: _containers.RepeatedCompositeFieldContainer[KnowledgeLibraryEntry]
    def __init__(self, user_id: _Optional[str] = ..., knowledge_dir: _Optional[str] = ..., created_at: _Optional[str] = ..., updated_at: _Optional[str] = ..., active_library_id: _Optional[str] = ..., active_knowledge_library: _Optional[_Union[KnowledgeLibraryEntry, _Mapping]] = ..., knowledge_libraries: _Optional[_Iterable[_Union[KnowledgeLibraryEntry, _Mapping]]] = ...) -> None: ...

class KnowledgeLibraryEntry(_message.Message):
    __slots__ = ("library_id", "user_id", "name", "knowledge_dir", "is_active", "created_at", "updated_at")
    LIBRARY_ID_FIELD_NUMBER: _ClassVar[int]
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    NAME_FIELD_NUMBER: _ClassVar[int]
    KNOWLEDGE_DIR_FIELD_NUMBER: _ClassVar[int]
    IS_ACTIVE_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    UPDATED_AT_FIELD_NUMBER: _ClassVar[int]
    library_id: str
    user_id: str
    name: str
    knowledge_dir: str
    is_active: bool
    created_at: str
    updated_at: str
    def __init__(self, library_id: _Optional[str] = ..., user_id: _Optional[str] = ..., name: _Optional[str] = ..., knowledge_dir: _Optional[str] = ..., is_active: bool = ..., created_at: _Optional[str] = ..., updated_at: _Optional[str] = ...) -> None: ...

class KnowledgeRebuildRequest(_message.Message):
    __slots__ = ("user_id", "knowledge_dir")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    KNOWLEDGE_DIR_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    knowledge_dir: str
    def __init__(self, user_id: _Optional[str] = ..., knowledge_dir: _Optional[str] = ...) -> None: ...

class KnowledgeFileUploadRequest(_message.Message):
    __slots__ = ("user_id", "filename", "relative_dir", "content")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    FILENAME_FIELD_NUMBER: _ClassVar[int]
    RELATIVE_DIR_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    filename: str
    relative_dir: str
    content: bytes
    def __init__(self, user_id: _Optional[str] = ..., filename: _Optional[str] = ..., relative_dir: _Optional[str] = ..., content: _Optional[bytes] = ...) -> None: ...

class KnowledgeRebuildResponse(_message.Message):
    __slots__ = ("user_id", "knowledge_dir", "frontmatter_dir", "frontmatter_files_seen", "frontmatter_files_written", "frontmatter_files_skipped", "files_seen", "files_ingested", "files_skipped", "chunks_created", "chunks_deleted", "uploaded_path", "library_id")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    KNOWLEDGE_DIR_FIELD_NUMBER: _ClassVar[int]
    FRONTMATTER_DIR_FIELD_NUMBER: _ClassVar[int]
    FRONTMATTER_FILES_SEEN_FIELD_NUMBER: _ClassVar[int]
    FRONTMATTER_FILES_WRITTEN_FIELD_NUMBER: _ClassVar[int]
    FRONTMATTER_FILES_SKIPPED_FIELD_NUMBER: _ClassVar[int]
    FILES_SEEN_FIELD_NUMBER: _ClassVar[int]
    FILES_INGESTED_FIELD_NUMBER: _ClassVar[int]
    FILES_SKIPPED_FIELD_NUMBER: _ClassVar[int]
    CHUNKS_CREATED_FIELD_NUMBER: _ClassVar[int]
    CHUNKS_DELETED_FIELD_NUMBER: _ClassVar[int]
    UPLOADED_PATH_FIELD_NUMBER: _ClassVar[int]
    LIBRARY_ID_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    knowledge_dir: str
    frontmatter_dir: str
    frontmatter_files_seen: int
    frontmatter_files_written: int
    frontmatter_files_skipped: int
    files_seen: int
    files_ingested: int
    files_skipped: int
    chunks_created: int
    chunks_deleted: int
    uploaded_path: str
    library_id: str
    def __init__(self, user_id: _Optional[str] = ..., knowledge_dir: _Optional[str] = ..., frontmatter_dir: _Optional[str] = ..., frontmatter_files_seen: _Optional[int] = ..., frontmatter_files_written: _Optional[int] = ..., frontmatter_files_skipped: _Optional[int] = ..., files_seen: _Optional[int] = ..., files_ingested: _Optional[int] = ..., files_skipped: _Optional[int] = ..., chunks_created: _Optional[int] = ..., chunks_deleted: _Optional[int] = ..., uploaded_path: _Optional[str] = ..., library_id: _Optional[str] = ...) -> None: ...

class KnowledgeFileTreeRequest(_message.Message):
    __slots__ = ("user_id",)
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    def __init__(self, user_id: _Optional[str] = ...) -> None: ...

class KnowledgeFileNode(_message.Message):
    __slots__ = ("name", "path", "is_dir", "mtime", "index_status", "size", "children")
    NAME_FIELD_NUMBER: _ClassVar[int]
    PATH_FIELD_NUMBER: _ClassVar[int]
    IS_DIR_FIELD_NUMBER: _ClassVar[int]
    MTIME_FIELD_NUMBER: _ClassVar[int]
    INDEX_STATUS_FIELD_NUMBER: _ClassVar[int]
    SIZE_FIELD_NUMBER: _ClassVar[int]
    CHILDREN_FIELD_NUMBER: _ClassVar[int]
    name: str
    path: str
    is_dir: bool
    mtime: str
    index_status: str
    size: int
    children: _containers.RepeatedCompositeFieldContainer[KnowledgeFileNode]
    def __init__(self, name: _Optional[str] = ..., path: _Optional[str] = ..., is_dir: bool = ..., mtime: _Optional[str] = ..., index_status: _Optional[str] = ..., size: _Optional[int] = ..., children: _Optional[_Iterable[_Union[KnowledgeFileNode, _Mapping]]] = ...) -> None: ...

class KnowledgeFileTreeResponse(_message.Message):
    __slots__ = ("tree",)
    TREE_FIELD_NUMBER: _ClassVar[int]
    tree: _containers.RepeatedCompositeFieldContainer[KnowledgeFileNode]
    def __init__(self, tree: _Optional[_Iterable[_Union[KnowledgeFileNode, _Mapping]]] = ...) -> None: ...

class KnowledgeFileContentRequest(_message.Message):
    __slots__ = ("user_id", "path")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    PATH_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    path: str
    def __init__(self, user_id: _Optional[str] = ..., path: _Optional[str] = ...) -> None: ...

class KnowledgeFileContentResponse(_message.Message):
    __slots__ = ("path", "content", "mtime", "size")
    PATH_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    MTIME_FIELD_NUMBER: _ClassVar[int]
    SIZE_FIELD_NUMBER: _ClassVar[int]
    path: str
    content: str
    mtime: str
    size: int
    def __init__(self, path: _Optional[str] = ..., content: _Optional[str] = ..., mtime: _Optional[str] = ..., size: _Optional[int] = ...) -> None: ...

class KnowledgeFileWriteRequest(_message.Message):
    __slots__ = ("user_id", "path", "content")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    PATH_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    path: str
    content: str
    def __init__(self, user_id: _Optional[str] = ..., path: _Optional[str] = ..., content: _Optional[str] = ...) -> None: ...

class KnowledgeFileCreateRequest(_message.Message):
    __slots__ = ("user_id", "path", "content")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    PATH_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    path: str
    content: str
    def __init__(self, user_id: _Optional[str] = ..., path: _Optional[str] = ..., content: _Optional[str] = ...) -> None: ...

class KnowledgeFolderCreateRequest(_message.Message):
    __slots__ = ("user_id", "path")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    PATH_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    path: str
    def __init__(self, user_id: _Optional[str] = ..., path: _Optional[str] = ...) -> None: ...

class KnowledgePathCopyRequest(_message.Message):
    __slots__ = ("user_id", "source_path", "target_path")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    SOURCE_PATH_FIELD_NUMBER: _ClassVar[int]
    TARGET_PATH_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    source_path: str
    target_path: str
    def __init__(self, user_id: _Optional[str] = ..., source_path: _Optional[str] = ..., target_path: _Optional[str] = ...) -> None: ...

class KnowledgePathDeleteRequest(_message.Message):
    __slots__ = ("user_id", "path")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    PATH_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    path: str
    def __init__(self, user_id: _Optional[str] = ..., path: _Optional[str] = ...) -> None: ...

class KnowledgePathRenameRequest(_message.Message):
    __slots__ = ("user_id", "source_path", "target_path")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    SOURCE_PATH_FIELD_NUMBER: _ClassVar[int]
    TARGET_PATH_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    source_path: str
    target_path: str
    def __init__(self, user_id: _Optional[str] = ..., source_path: _Optional[str] = ..., target_path: _Optional[str] = ...) -> None: ...

class SystemPromptRequest(_message.Message):
    __slots__ = ("user_id",)
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    def __init__(self, user_id: _Optional[str] = ...) -> None: ...

class SystemPromptEntryResponse(_message.Message):
    __slots__ = ("prompt_id", "content", "created_at")
    PROMPT_ID_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    prompt_id: str
    content: str
    created_at: str
    def __init__(self, prompt_id: _Optional[str] = ..., content: _Optional[str] = ..., created_at: _Optional[str] = ...) -> None: ...

class SystemPromptEntriesResponse(_message.Message):
    __slots__ = ("entries",)
    ENTRIES_FIELD_NUMBER: _ClassVar[int]
    entries: _containers.RepeatedCompositeFieldContainer[SystemPromptEntryResponse]
    def __init__(self, entries: _Optional[_Iterable[_Union[SystemPromptEntryResponse, _Mapping]]] = ...) -> None: ...

class SystemPromptAddRequest(_message.Message):
    __slots__ = ("user_id", "content")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    content: str
    def __init__(self, user_id: _Optional[str] = ..., content: _Optional[str] = ...) -> None: ...

class SystemPromptDeleteRequest(_message.Message):
    __slots__ = ("prompt_id",)
    PROMPT_ID_FIELD_NUMBER: _ClassVar[int]
    prompt_id: str
    def __init__(self, prompt_id: _Optional[str] = ...) -> None: ...

class MemoryListRequest(_message.Message):
    __slots__ = ("user_id",)
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    def __init__(self, user_id: _Optional[str] = ...) -> None: ...

class MemoryEntryResponse(_message.Message):
    __slots__ = ("memory_id", "content", "importance", "created_at")
    MEMORY_ID_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    IMPORTANCE_FIELD_NUMBER: _ClassVar[int]
    CREATED_AT_FIELD_NUMBER: _ClassVar[int]
    memory_id: str
    content: str
    importance: float
    created_at: str
    def __init__(self, memory_id: _Optional[str] = ..., content: _Optional[str] = ..., importance: _Optional[float] = ..., created_at: _Optional[str] = ...) -> None: ...

class MemoryListResponse(_message.Message):
    __slots__ = ("entries",)
    ENTRIES_FIELD_NUMBER: _ClassVar[int]
    entries: _containers.RepeatedCompositeFieldContainer[MemoryEntryResponse]
    def __init__(self, entries: _Optional[_Iterable[_Union[MemoryEntryResponse, _Mapping]]] = ...) -> None: ...

class MemoryAddRequest(_message.Message):
    __slots__ = ("user_id", "content", "importance")
    USER_ID_FIELD_NUMBER: _ClassVar[int]
    CONTENT_FIELD_NUMBER: _ClassVar[int]
    IMPORTANCE_FIELD_NUMBER: _ClassVar[int]
    user_id: str
    content: str
    importance: float
    def __init__(self, user_id: _Optional[str] = ..., content: _Optional[str] = ..., importance: _Optional[float] = ...) -> None: ...

class MemoryDeleteRequest(_message.Message):
    __slots__ = ("memory_id",)
    MEMORY_ID_FIELD_NUMBER: _ClassVar[int]
    memory_id: str
    def __init__(self, memory_id: _Optional[str] = ...) -> None: ...

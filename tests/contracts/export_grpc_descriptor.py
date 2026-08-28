"""导出规范化 protobuf 文件描述符快照。

用法：在项目根目录执行 ``python -m tests.contracts.export_grpc_descriptor``。
输出包含 AgentService proto 及其依赖，供拆分 servicer 前后比较协议兼容性。
"""

from __future__ import annotations

from google.protobuf.descriptor import FileDescriptor
from google.protobuf.descriptor_pb2 import FileDescriptorSet
from google.protobuf.json_format import MessageToDict

from tests.contracts.common import write_snapshot


def _collect_descriptors(root: FileDescriptor) -> list[FileDescriptor]:
    """按文件名稳定排序递归收集 proto 文件及依赖。"""

    collected: dict[str, FileDescriptor] = {}

    def visit(descriptor: FileDescriptor) -> None:
        """将 descriptor 及尚未访问的依赖加入集合。"""

        if descriptor.name in collected:
            return
        collected[descriptor.name] = descriptor
        for dependency in descriptor.dependencies:
            visit(dependency)

    visit(root)
    return [collected[name] for name in sorted(collected)]


def main() -> int:
    """构建 FileDescriptorSet 并写入稳定 JSON。"""

    from agent_service.api.grpc.agent_service_pb2 import DESCRIPTOR

    descriptor_set = FileDescriptorSet()
    for descriptor in _collect_descriptors(DESCRIPTOR):
        descriptor.CopyToProto(descriptor_set.file.add())
    write_snapshot(
        "grpc_descriptor.json",
        MessageToDict(descriptor_set, preserving_proto_field_name=True),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

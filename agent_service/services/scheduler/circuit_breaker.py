"""
LLM 调度器熔断器模块。

功能说明:
本文件实现简单的熔断器状态机,用于在连续 429、overload、timeout 等可恢复错误
出现时临时阻止新任务继续压垮上游模型服务。第一版支持可选 Redis 持久化熔断状态,
便于多进程实例共享最基础的失败窗口信息。

使用说明:
由 `scheduler.py` 内部使用,业务代码不直接调用。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
from threading import Lock
from typing import Any


def _utc_now() -> datetime:
    """返回当前 UTC 时间。"""

    return datetime.now(timezone.utc)


@dataclass(slots=True)
class CircuitBreakerSnapshot:
    """
    熔断器状态快照。

    state: `closed`、`open` 或 `half_open`。
    consecutive_failures: 连续失败次数。
    opened_at: 熔断器打开时间。
    """

    state: str = "closed"
    consecutive_failures: int = 0
    opened_at: datetime | None = None

    def to_json(self) -> str:
        """将快照序列化为 JSON 字符串。"""

        payload = {
            "state": self.state,
            "consecutive_failures": self.consecutive_failures,
            "opened_at": self.opened_at.isoformat() if self.opened_at else None,
        }
        return json.dumps(payload, ensure_ascii=False)

    @classmethod
    def from_json(cls, payload: str | None) -> "CircuitBreakerSnapshot":
        """从 JSON 字符串恢复快照。"""

        if not payload:
            return cls()
        raw = json.loads(payload)
        opened_at_raw = raw.get("opened_at")
        opened_at = None
        if opened_at_raw:
            opened_at = datetime.fromisoformat(str(opened_at_raw).replace("Z", "+00:00"))
        return cls(
            state=str(raw.get("state", "closed")),
            consecutive_failures=int(raw.get("consecutive_failures", 0)),
            opened_at=opened_at,
        )


class RedisCircuitBreakerStore:
    """
    Redis 熔断状态存储。

    redis_url: Redis 连接地址。
    key_prefix: Redis 键前缀。
    """

    def __init__(self, *, redis_url: str, key_prefix: str) -> None:
        """初始化 Redis 客户端。"""

        try:
            from redis import Redis
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("启用 Redis 调度状态前请先安装 redis 依赖。") from exc

        self.client = Redis.from_url(redis_url, decode_responses=True)
        self.key_prefix = key_prefix

    def load(self, breaker_name: str) -> CircuitBreakerSnapshot:
        """读取指定熔断器快照。"""

        payload = self.client.get(self._key(breaker_name))
        return CircuitBreakerSnapshot.from_json(payload)

    def save(self, breaker_name: str, snapshot: CircuitBreakerSnapshot, *, ttl_seconds: int) -> None:
        """保存指定熔断器快照。"""

        self.client.set(self._key(breaker_name), snapshot.to_json(), ex=max(ttl_seconds, 1))

    def _key(self, breaker_name: str) -> str:
        """构造 Redis 键名。"""

        return f"{self.key_prefix}:breaker:{breaker_name}"


class CircuitBreaker:
    """
    线程安全熔断器。

    name: 熔断器名称,通常对应任务类型。
    failure_threshold: 连续失败达到多少次后打开熔断器。
    recovery_seconds: 熔断后多久允许半开探测。
    store: 可选 Redis 状态存储。
    """

    def __init__(
        self,
        *,
        name: str,
        failure_threshold: int,
        recovery_seconds: int,
        store: RedisCircuitBreakerStore | None = None,
    ) -> None:
        """初始化熔断器。"""

        self.name = name
        self.failure_threshold = max(failure_threshold, 1)
        self.recovery_seconds = max(recovery_seconds, 1)
        self.store = store
        self._lock = Lock()
        self._half_open_inflight = False
        self._snapshot = self._load_snapshot()

    def allow_request(self) -> bool:
        """判断当前是否允许放行新的任务请求。"""

        with self._lock:
            snapshot = self._load_snapshot()
            now = _utc_now()
            if snapshot.state == "closed":
                self._snapshot = snapshot
                return True
            if snapshot.state == "open":
                if snapshot.opened_at is None:
                    snapshot.opened_at = now
                if now - snapshot.opened_at < timedelta(seconds=self.recovery_seconds):
                    self._snapshot = snapshot
                    return False
                snapshot.state = "half_open"
                snapshot.consecutive_failures = 0
                self._persist(snapshot)
            if self._half_open_inflight:
                return False
            self._half_open_inflight = snapshot.state == "half_open"
            self._snapshot = snapshot
            return True

    def record_success(self) -> None:
        """记录一次成功请求,关闭熔断器。"""

        with self._lock:
            snapshot = CircuitBreakerSnapshot(state="closed", consecutive_failures=0, opened_at=None)
            self._half_open_inflight = False
            self._snapshot = snapshot
            self._persist(snapshot)

    def record_failure(self) -> None:
        """记录一次失败请求,必要时打开熔断器。"""

        with self._lock:
            snapshot = self._load_snapshot()
            snapshot.consecutive_failures += 1
            now = _utc_now()
            if snapshot.state == "half_open" or snapshot.consecutive_failures >= self.failure_threshold:
                snapshot.state = "open"
                snapshot.opened_at = now
            self._half_open_inflight = False
            self._snapshot = snapshot
            self._persist(snapshot)

    def _load_snapshot(self) -> CircuitBreakerSnapshot:
        """读取当前熔断快照。"""

        if self.store is None:
            return self._snapshot if hasattr(self, "_snapshot") else CircuitBreakerSnapshot()
        return self.store.load(self.name)

    def _persist(self, snapshot: CircuitBreakerSnapshot) -> None:
        """持久化当前熔断快照。"""

        if self.store is None:
            return
        self.store.save(
            self.name,
            snapshot,
            ttl_seconds=self.recovery_seconds * 4,
        )

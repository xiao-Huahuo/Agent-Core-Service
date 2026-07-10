"""
统一日志服务模块。

功能说明:
本文件提供全局日志系统的初始化入口 `setup_logging()`,负责根据 `AgentConfig.LoggingConfig`
配置控制台与文件双通道日志输出、格式选择(plain/json)、文件轮转(按大小/按天)以及
各模块独立日志级别覆写。所有业务代码应通过 `logging.getLogger(__name__)` 获取 logger,
无需直接依赖本模块。

使用说明:
在服务入口 `main.py` 的 lifespan 最早阶段调用一次 `setup_logging(config)` 即可:

    from agent_service.services.logging_service import setup_logging
    from agent_service.core.agent_config import AgentConfig

    config = AgentConfig.load_config(ensure_models=False)
    setup_logging(config)

此后各模块直接使用标准库 logging:

    import logging
    logger = logging.getLogger(__name__)
    logger.info("Agent 启动完成")
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import sys
from pathlib import Path
from typing import Any

from agent_service.core.agent_config import AgentConfig

_initialized: bool = False


def setup_logging(config: AgentConfig) -> None:
    """
    根据全局配置初始化日志系统。

    该函数只应调用一次,重复调用不会重新初始化。
    初始化后会:
    - 清空已注册的 handler,避免重复添加。
    - 设置根 logger 的全局日志级别。
    - 根据配置添加控制台 handler (支持 plain / structured 格式)。
    - 根据配置添加文件 handler (支持 json / plain 格式, size / daily 轮转)。
    - 应用 module_levels 对各模块 logger 设置独立级别。

    config: 已加载的全局 AgentConfig 实例。
    """

    global _initialized
    if _initialized:
        return
    _initialized = True

    log_config = config.logging
    log_dir = config.storage.log_dir
    log_dir.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(_resolve_level(log_config.level))

    formatter_console = _build_console_formatter(log_config.console_format)
    formatter_file = _build_file_formatter(log_config.file_format)

    if log_config.enable_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_level = _resolve_level(log_config.console_level) if log_config.console_level else None
        console_handler.setLevel(console_level or _resolve_level(log_config.level))
        console_handler.setFormatter(formatter_console)
        root_logger.addHandler(console_handler)

    if log_config.enable_file:
        log_file_path = log_dir / "agent_service.log"
        file_handler = _build_file_handler(log_file_path, log_config)
        file_level = _resolve_level(log_config.file_level)
        file_handler.setLevel(file_level)
        file_handler.setFormatter(formatter_file)
        root_logger.addHandler(file_handler)

    for module_name, module_level in log_config.module_levels.items():
        logging.getLogger(module_name).setLevel(_resolve_level(module_level))

    root_logger.info(
        "日志系统已初始化 | level=%s console=%s file=%s log_dir=%s",
        log_config.level,
        log_config.enable_console,
        log_config.enable_file,
        str(log_dir),
    )


def is_initialized() -> bool:
    """返回日志系统是否已完成初始化。"""

    return _initialized


def _resolve_level(level_name: str) -> int:
    """
    将日志级别字符串转换为标准库 logging 级别常量。

    level_name: 日志级别字符串,如 DEBUG / INFO / WARNING / ERROR / CRITICAL。
    """

    return getattr(logging, level_name.strip().upper(), logging.INFO)


def _build_console_formatter(format_type: str) -> logging.Formatter:
    """
    构建控制台日志格式化器。

    format_type: plain 输出人类可读格式; structured 输出 JSON 行。
    """

    if format_type == "structured":
        return _StructuredFormatter()
    return logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _build_file_formatter(format_type: str) -> logging.Formatter:
    """
    构建文件日志格式化器。

    format_type: json 输出 JSON 行便于日志采集; plain 输出与 console plain 一致的格式。
    """

    if format_type == "json":
        return _JsonFileFormatter()
    return logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _build_file_handler(log_file_path: Path, log_config: AgentConfig.LoggingConfig) -> logging.Handler:
    """
    根据轮转策略构建文件日志 handler。

    log_file_path: 日志文件完整路径。
    log_config: 日志配置子对象。
    """

    if log_config.file_rotation == "daily":
        handler = logging.handlers.TimedRotatingFileHandler(
            filename=str(log_file_path),
            when=log_config.file_daily_when,
            backupCount=log_config.file_daily_backup_count,
            encoding="utf-8",
        )
    else:
        handler = logging.handlers.RotatingFileHandler(
            filename=str(log_file_path),
            maxBytes=log_config.file_max_bytes,
            backupCount=log_config.file_backup_count,
            encoding="utf-8",
        )
    return handler


class _JsonFileFormatter(logging.Formatter):
    """
    文件 JSON 行格式化器。

    每行输出一条 JSON 对象,包含 timestamp / level / logger / module / message
    以及 exc_info 异常信息(如有),方便日志采集系统(如 ELK / Loki)解析。
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": _format_timestamp(self.formatTime(record)),
            "level": record.levelname,
            "logger": record.name,
            "module": f"{record.module}:{record.lineno}",
            "message": record.getMessage(),
        }
        if record.exc_info and record.exc_info[0]:
            import traceback

            log_entry["exception"] = "".join(traceback.format_exception(*record.exc_info))
        return json.dumps(log_entry, ensure_ascii=False)


class _StructuredFormatter(logging.Formatter):
    """
    控制台结构化(JSON 行)格式化器。

    与 _JsonFileFormatter 类似但输出到 stdout,适合容器环境通过 stdout 采集日志。
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": _format_timestamp(self.formatTime(record)),
            "level": record.levelname,
            "logger": record.name,
            "module": f"{record.module}:{record.lineno}",
            "message": record.getMessage(),
        }
        return json.dumps(log_entry, ensure_ascii=False)


def _format_timestamp(formatted_time: str) -> str:
    """
    将 logging.Formatter 的默认 formatTime 输出转换为 ISO 8601 微秒格式。

    formatted_time: logging.Formatter.formatTime() 返回的默认时间字符串,
        格式为 "2003-07-08 16:49:45,896"。

    返回值: "2003-07-08T16:49:45.896000Z"。
    """

    return formatted_time.replace(" ", "T", 1).replace(",", ".") + "000Z"


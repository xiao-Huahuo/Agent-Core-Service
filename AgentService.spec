# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 构建配置 — 将后端和前端静态资源打包为单个 exe。

使用说明:
先构建 editor/dist,再执行 `pyinstaller AgentService.spec`。
构建产物输出到项目根目录的 dist/AgentService.exe。
默认 resources 由 Electron 安装包作为外置模板携带,不进入后端 exe。
"""

import atexit
from pathlib import Path
import shutil
import tempfile

# SPECPATH 由 PyInstaller 在 exec spec 前注入,指向 spec 文件所在目录
_project_root = Path(SPECPATH)  # noqa: F821


def _required_data_dir(relative_path: str) -> tuple[str, str]:
    """返回 PyInstaller datas 目录元组,并在目录缺失时给出明确错误。"""

    source = _project_root / relative_path
    if not source.is_dir():
        raise FileNotFoundError(
            f"Required build asset directory is missing: {source}. "
            f"Build it before running PyInstaller."
        )
    return (str(source), relative_path.replace("\\", "/"))


def _required_data_file(relative_path: str) -> tuple[str, str]:
    """返回根目录数据文件元组,并在文件缺失时中止构建。"""

    source = _project_root / relative_path
    if not source.is_file():
        raise FileNotFoundError(f"Required build asset file is missing: {source}")
    return (str(source), ".")


def _snapshot_required_data_dir(relative_path: str) -> tuple[str, str]:
    """复制易被并发构建改写的数据目录,供本次构建稳定读取。"""

    source, destination = _required_data_dir(relative_path)
    snapshot_root = Path(tempfile.mkdtemp(prefix="metaweave-pyinstaller-"))
    atexit.register(shutil.rmtree, snapshot_root, ignore_errors=True)
    snapshot = snapshot_root / relative_path
    shutil.copytree(source, snapshot)
    if not (snapshot / "index.html").is_file():
        raise FileNotFoundError(f"Frontend build snapshot is incomplete: {snapshot}")
    return (str(snapshot), destination)


a = Analysis(
    ['main.py'],
    pathex=[str(_project_root)],
    binaries=[],
    # 只打包程序和前端静态资源。resources/ 与 runtime/ 都是用户可见目录:
    # resources/ 由 Electron 安装包外置携带默认模板,runtime/ 首次运行生成。
    datas=[
        _snapshot_required_data_dir('editor/dist'),
        _required_data_dir('agent_service/core/db/alembic'),
        _required_data_file('alembic.ini'),
    ],
    hiddenimports=['xlrd', 'torchvision'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pytest',
        'pip',
        'torchaudio',
        'nvidia',
        'caffe2',
        'grpcio_tools',
        'grpcio_tests',
        'mypy',
        'ruff',
        'IPython',
        'jupyter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    a.zipfiles,
    name='AgentService',
    icon='editor/src/assets/icons/app.ico',
    console=True,
    debug=False,
)

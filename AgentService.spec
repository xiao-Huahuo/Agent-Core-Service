# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 构建配置 — 将后端和前端静态资源打包为单个 exe。

使用说明:
先构建 editor/dist,再执行 `pyinstaller AgentService.spec`。
构建产物输出到项目根目录的 dist/AgentService.exe。
默认 resources 由 Electron 安装包作为外置模板携带,不进入后端 exe。
"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

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


a = Analysis(
    ['main.py'],
    pathex=[str(_project_root)],
    binaries=[],
    # 只打包程序和前端静态资源。resources/ 与 runtime/ 都是用户可见目录:
    # resources/ 由 Electron 安装包外置携带默认模板,runtime/ 首次运行生成。
    datas=[
        _required_data_dir('editor/dist'),
    ],
    hiddenimports=collect_submodules('agent_service'),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pytest',
        'pip',
        'torchaudio',
        'torchvision',
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

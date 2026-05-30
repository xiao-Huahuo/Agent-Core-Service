# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller 构建配置 — 将后端 + 前端静态资源打包为单个 exe。"""

from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

# SPECPATH 由 PyInstaller 在 exec spec 前注入,指向 spec 文件所在目录
_project_root = Path(SPECPATH)  # noqa: F821

a = Analysis(
    ['main.py'],
    pathex=[str(_project_root)],
    binaries=[],
    datas=[
        ('console/dist', 'console/dist'),
        ('resources', 'resources'),
    ],
    hiddenimports=collect_submodules('agent_service'),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'pytest',
        'pip',
        'setuptools',
        'wheel',
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
    icon=None,
    console=True,
    debug=False,
)

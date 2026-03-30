# -*- mode: python ; coding: utf-8 -*-
import os
from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
    copy_metadata,
)

PROJECT_ROOT = Path.cwd()
STAGE_ROOT = PROJECT_ROOT / "build" / "staging" / "basic"
INCLUDE_HYBRID = os.environ.get("DYS_FR_INCLUDE_HYBRID", "0").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}

if not STAGE_ROOT.exists():
    raise SystemExit(
        f"Missing staged runtime assets at {STAGE_ROOT}. "
        "Run packaging/windows/stage_assets.py before invoking PyInstaller."
    )


def include_streamlit_submodule(name: str) -> bool:
    return not name.startswith((
        "streamlit.external.langchain",
        "streamlit.hello",
        "streamlit.testing",
    ))


def include_spacy_submodule(name: str) -> bool:
    return not name.startswith("spacy.tests")


datas = [
    (str(PROJECT_ROOT / "config.yaml"), "."),
    (str(PROJECT_ROOT / "app.py"), "."),
    (str(STAGE_ROOT / "resources"), "resources"),
]

if (STAGE_ROOT / "runtime").exists():
    datas.append((str(STAGE_ROOT / "runtime"), "runtime"))

datas += collect_data_files("streamlit")
datas += collect_data_files("spacy")
datas += copy_metadata("streamlit")
datas += copy_metadata("spacy")
datas += copy_metadata("language_tool_python")

hiddenimports = []
hiddenimports += collect_submodules("streamlit", filter=include_streamlit_submodule)
hiddenimports += collect_submodules("spacy", filter=include_spacy_submodule)
hiddenimports += [
    "streamlit.web.cli",
    "streamlit.runtime.runtime",
    "watchdog.observers.winapi",
]

excludes = ["tests", "pytest", "tkinter"]
if not INCLUDE_HYBRID:
    excludes += [
        "llama_cpp",
        "llama_cpp_python",
        "ollama",
        "src.improvers.llm_improver",
        "src.improvers.ollama_improver",
    ]

binaries = []
binaries += collect_dynamic_libs("pyarrow")
binaries += collect_dynamic_libs("numpy")

block_cipher = None

a = Analysis(
    [str(PROJECT_ROOT / "runner.py")],
    pathex=[str(PROJECT_ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="DYS-fr",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    name="DYS-fr",
)

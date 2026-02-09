# -*- mode: python ; coding: utf-8 -*-

from pathlib import Path

from PyInstaller.utils.hooks import (
    collect_data_files,
    collect_dynamic_libs,
    collect_submodules,
    copy_metadata,
)


PROJECT_ROOT = Path(SPECPATH).resolve().parents[1]


datas = [
    (str(PROJECT_ROOT / "app.py"), "."),
    (str(PROJECT_ROOT / "config.yaml"), "."),
    (str(PROJECT_ROOT / "resources"), "resources"),
]


def safe_copy_metadata(dist_name: str):
    """Copy package metadata if available, otherwise continue without failing the build."""
    try:
        return copy_metadata(dist_name)
    except Exception as exc:
        print(f"[build.spec] Metadata unavailable for '{dist_name}': {exc}")
        return []


def safe_collect_data(package_name: str, includes=None):
    """Collect non-Python package data needed at runtime (templates, static files, etc.)."""
    try:
        if includes is None:
            return collect_data_files(package_name)
        return collect_data_files(package_name, includes=includes)
    except Exception as exc:
        print(f"[build.spec] Data collection unavailable for '{package_name}': {exc}")
        return []


def safe_collect_submodules(package_name: str):
    """Collect submodules while tolerating optional dependency import errors."""
    try:
        return collect_submodules(package_name)
    except Exception as exc:
        print(f"[build.spec] Submodule collection unavailable for '{package_name}': {exc}")
        return []


def safe_collect_dynamic_libs(package_name: str):
    """Collect dynamic libraries for packages that load DLLs at runtime."""
    try:
        return collect_dynamic_libs(package_name)
    except Exception as exc:
        print(f"[build.spec] Dynamic library collection unavailable for '{package_name}': {exc}")
        return []


for dist_name in (
    "streamlit",
    "spacy",
    "language_tool_python",
    "llama_cpp_python",
    "ollama",
):
    datas += safe_copy_metadata(dist_name)

# Streamlit serves its frontend from streamlit/static/index.html at runtime.
datas += safe_collect_data("streamlit", includes=["static/**"])
# llama-cpp-python expects this folder for os.add_dll_directory(...)
datas += safe_collect_data("llama_cpp", includes=["lib/**"])

binaries = []
binaries += safe_collect_dynamic_libs("llama_cpp")
hiddenimports = sorted(
    set(
        safe_collect_submodules("src")
        + safe_collect_submodules("src.ui")
        + safe_collect_submodules("src.services")
        + safe_collect_submodules("src.improvers")
        + safe_collect_submodules("src.guardrails")
        + safe_collect_submodules("src.utils")
        + safe_collect_submodules("streamlit")
    )
)
excludes = [
    "tensorflow",
    "keras",
    "torch",
    "cv2",
    "sklearn",
    "scipy",
    "matplotlib",
    "IPython",
    "notebook",
    "jupyter",
]

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
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

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
    console=True,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="DYS-fr",
)

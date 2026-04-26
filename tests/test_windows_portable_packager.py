from __future__ import annotations

import hashlib
import importlib.util
import sys
import zipfile
from pathlib import Path

MODULE_PATH = Path(__file__).parent.parent / "packaging" / "windows" / "package_portable.py"
spec = importlib.util.spec_from_file_location("package_portable", MODULE_PATH)
assert spec is not None
assert spec.loader is not None
package_portable = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = package_portable
spec.loader.exec_module(package_portable)


def test_component_manifest_includes_component_metadata(tmp_path):
    artifact = tmp_path / "component.zip"
    artifact.write_bytes(b"zip")
    component = {
        "id": "core",
        "kind": "zip",
        "display_name": "core runtime",
        "required": True,
        "url": "https://example.test/core.zip",
        "target": "",
        "size": artifact.stat().st_size,
        "sha256": hashlib.sha256(artifact.read_bytes()).hexdigest(),
        "validation_files": [{"path": "DYS-fr-runtime.exe", "size": 3}],
    }

    manifest = package_portable.build_components_manifest(
        app_version="1.2.3",
        flavor="hybrid",
        runtime_exe_name="DYS-fr-runtime.exe",
        components=[component],
    )

    assert manifest["schema"] == 2
    assert manifest["version"] == "1.2.3"
    assert manifest["flavor"] == "hybrid"
    assert manifest["runtime_exe"] == "DYS-fr-runtime.exe"
    assert manifest["components"] == [component]
    assert manifest["required_files"] == component["validation_files"]


def test_core_zip_preserves_runtime_layout_and_excludes_heavy_assets(tmp_path):
    runtime_root = tmp_path / "runtime"
    internal = runtime_root / "_internal"
    internal.mkdir(parents=True)
    (runtime_root / "DYS-fr-runtime.exe").write_bytes(b"exe")
    (internal / "app.py").write_text("app", encoding="utf-8")
    (internal / "config.yaml").write_text("cfg", encoding="utf-8")
    llama_lib = internal / "llama_cpp" / "lib"
    llama_lib.mkdir(parents=True)
    (llama_lib / "llama.dll").write_bytes(b"dll")
    zip_path = tmp_path / "core.zip"

    package_portable.assert_core_is_light(runtime_root)
    package_portable.write_zip_from_root(source_root=runtime_root, zip_path=zip_path)

    with zipfile.ZipFile(zip_path) as archive:
        assert sorted(archive.namelist()) == [
            "DYS-fr-runtime.exe",
            "_internal/app.py",
            "_internal/config.yaml",
            "_internal/llama_cpp/lib/llama.dll",
        ]


def test_hybrid_core_validation_requires_llama_cpp_runtime(tmp_path):
    runtime_root = tmp_path / "runtime"
    internal = runtime_root / "_internal"
    internal.mkdir(parents=True)
    (runtime_root / "DYS-fr-runtime.exe").write_bytes(b"exe")
    (internal / "app.py").write_text("app", encoding="utf-8")
    (internal / "config.yaml").write_text("cfg", encoding="utf-8")

    component = package_portable.ComponentPackage(
        component_id="core",
        kind="zip",
        display_name="core runtime",
        source=runtime_root,
        artifact=tmp_path / "core.zip",
        url="https://example.test/core.zip",
        target="",
        validation_paths=package_portable.CORE_VALIDATION_PATHS
        + package_portable.HYBRID_CORE_VALIDATION_PATHS,
    )

    try:
        package_portable.component_validation_files(component)
    except FileNotFoundError as exc:
        assert "llama.dll" in str(exc)
    else:  # pragma: no cover - explicit failure branch
        raise AssertionError("Expected hybrid core validation to require llama_cpp runtime files")


def test_core_light_check_rejects_staged_heavy_assets(tmp_path):
    runtime_root = tmp_path / "runtime"
    heavy_dir = runtime_root / "_internal" / "resources" / "models"
    heavy_dir.mkdir(parents=True)
    (heavy_dir / "model.gguf").write_bytes(b"model")

    try:
        package_portable.assert_core_is_light(runtime_root)
    except RuntimeError as exc:
        assert "heavy staged assets" in str(exc)
    else:  # pragma: no cover - explicit failure branch
        raise AssertionError("Expected assert_core_is_light to reject heavy assets")


def test_asset_zip_uses_final_internal_target_path(tmp_path):
    source = tmp_path / "jre"
    bin_dir = source / "bin"
    bin_dir.mkdir(parents=True)
    (bin_dir / "java.exe").write_bytes(b"java")
    zip_path = tmp_path / "jre.zip"

    package_portable.write_zip_from_root(
        source_root=source,
        zip_path=zip_path,
        install_prefix="_internal/runtime/jre",
    )

    with zipfile.ZipFile(zip_path) as archive:
        assert archive.namelist() == ["_internal/runtime/jre/bin/java.exe"]

#!/usr/bin/env python
from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

MANIFEST_NAME = "DYS-fr-runtime-manifest.json"
DEFAULT_RUNTIME_EXE = "DYS-fr-runtime.exe"
DEFAULT_MISTRAL_URL = (
    "https://huggingface.co/bartowski/Mistral-7B-Instruct-v0.3-GGUF/resolve/main/"
    "Mistral-7B-Instruct-v0.3-Q4_K_M.gguf"
)

CORE_VALIDATION_PATHS = (
    DEFAULT_RUNTIME_EXE,
    "_internal/app.py",
    "_internal/config.yaml",
)
JRE_VALIDATION_PATHS = (
    "_internal/runtime/jre/bin/java.exe",
    "_internal/runtime/jre/bin/javaw.exe",
)
LT_VALIDATION_PATHS = (
    "_internal/resources/languagetool/languagetool-server.jar",
)
SPACY_VALIDATION_PATHS = (
    "_internal/resources/spacy/models/fr_core_news_md/config.cfg",
)
MISTRAL_VALIDATION_PATHS = (
    "_internal/resources/models/Mistral-7B-Instruct-v0.3-Q4_K_M.gguf",
)


@dataclass(frozen=True)
class ComponentPackage:
    component_id: str
    kind: str
    display_name: str
    source: Path
    artifact: Path | None
    url: str
    target: str
    validation_paths: tuple[str, ...]


def iter_files(root: Path) -> list[Path]:
    return sorted(path for path in root.rglob("*") if path.is_file())


def relpath(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def prefixed_relpath(path: Path, root: Path, prefix: str) -> str:
    runtime_rel = relpath(path, root)
    return f"{prefix.rstrip('/')}/{runtime_rel}" if prefix else runtime_rel


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def file_entry(path: Path, install_path: str) -> dict[str, int | str]:
    return {"path": install_path.replace("\\", "/"), "size": path.stat().st_size}


def validation_files_for(root: Path, validation_paths: Iterable[str]) -> list[dict[str, int | str]]:
    entries: list[dict[str, int | str]] = []
    for item in validation_paths:
        path = root / item
        if not path.exists():
            raise FileNotFoundError(f"Validation file missing from component source: {path}")
        entries.append(file_entry(path, item))
    return entries


def component_validation_files(component: ComponentPackage) -> list[dict[str, int | str]]:
    entries: list[dict[str, int | str]] = []
    target_prefix = component.target.strip("/")
    for item in component.validation_paths:
        normalized = item.replace("\\", "/")
        if target_prefix:
            prefix = f"{target_prefix}/"
            if not normalized.startswith(prefix):
                raise ValueError(f"Validation path '{item}' is outside component target '{component.target}'")
            source_rel = normalized[len(prefix) :]
        else:
            source_rel = normalized
        source_path = component.source / source_rel
        if not source_path.exists():
            raise FileNotFoundError(f"Validation file missing from component source: {source_path}")
        entries.append(file_entry(source_path, normalized))
    return entries


def write_zip_from_root(*, source_root: Path, zip_path: Path, install_prefix: str = "") -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
        for path in iter_files(source_root):
            archive.write(path, prefixed_relpath(path, source_root, install_prefix))


def assert_core_is_light(runtime_root: Path) -> None:
    forbidden = (
        runtime_root / "_internal" / "runtime" / "jre",
        runtime_root / "_internal" / "resources" / "languagetool",
        runtime_root / "_internal" / "resources" / "spacy" / "models",
        runtime_root / "_internal" / "resources" / "models",
    )
    present = [str(path) for path in forbidden if path.exists()]
    if present:
        raise RuntimeError("Core runtime contains heavy staged assets:\n" + "\n".join(present))


def build_zip_component(component: ComponentPackage) -> dict[str, object]:
    if component.artifact is None:
        raise ValueError("ZIP components require an artifact path.")
    write_zip_from_root(
        source_root=component.source,
        zip_path=component.artifact,
        install_prefix=component.target,
    )
    validation_files = component_validation_files(component)
    return {
        "id": component.component_id,
        "kind": component.kind,
        "display_name": component.display_name,
        "required": True,
        "url": component.url,
        "target": component.target,
        "size": component.artifact.stat().st_size,
        "sha256": sha256_file(component.artifact),
        "validation_files": validation_files,
    }


def build_file_component(component: ComponentPackage) -> dict[str, object]:
    if not component.source.exists():
        raise FileNotFoundError(f"File component source is missing: {component.source}")
    return {
        "id": component.component_id,
        "kind": component.kind,
        "display_name": component.display_name,
        "required": True,
        "url": component.url,
        "target": component.target,
        "size": component.source.stat().st_size,
        "sha256": sha256_file(component.source),
        "validation_files": [file_entry(component.source, component.target)],
    }


def build_components_manifest(
    *,
    app_version: str,
    flavor: str,
    runtime_exe_name: str,
    components: list[dict[str, object]],
) -> dict[str, object]:
    required_files: list[dict[str, int | str]] = []
    for component in components:
        required_files.extend(component["validation_files"])  # type: ignore[arg-type]

    return {
        "schema": 2,
        "app": "DYS-fr",
        "version": app_version,
        "flavor": flavor,
        "runtime_exe": runtime_exe_name,
        "components": components,
        "required_files": required_files,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build componentized DYS-fr Windows runtime assets.")
    parser.add_argument("--runtime-root", required=True, help="PyInstaller core runtime root.")
    parser.add_argument("--stage-root", required=True, help="Staged assets root produced by stage_assets.py.")
    parser.add_argument("--output-dir", required=True, help="Directory where component artifacts are written.")
    parser.add_argument("--output-manifest", required=True, help="Component manifest output path.")
    parser.add_argument("--app-version", required=True)
    parser.add_argument("--flavor", choices=["basic", "hybrid"], required=True)
    parser.add_argument("--release-base-url", required=True)
    parser.add_argument("--runtime-exe-name", default=DEFAULT_RUNTIME_EXE)
    parser.add_argument("--mistral-url", default=DEFAULT_MISTRAL_URL)
    args = parser.parse_args()

    runtime_root = Path(args.runtime_root).resolve()
    stage_root = Path(args.stage_root).resolve()
    output_dir = Path(args.output_dir).resolve()
    output_manifest = Path(args.output_manifest).resolve()
    release_base_url = args.release_base_url.rstrip("/")

    if not (runtime_root / args.runtime_exe_name).exists():
        raise FileNotFoundError(f"Runtime executable not found: {runtime_root / args.runtime_exe_name}")
    assert_core_is_light(runtime_root)

    output_dir.mkdir(parents=True, exist_ok=True)
    component_specs: list[ComponentPackage] = [
        ComponentPackage(
            component_id="core",
            kind="zip",
            display_name="core runtime",
            source=runtime_root,
            artifact=output_dir / f"DYS-fr-core-runtime-{args.app_version}-{args.flavor}.zip",
            url=f"{release_base_url}/DYS-fr-core-runtime-{args.app_version}-{args.flavor}.zip",
            target="",
            validation_paths=CORE_VALIDATION_PATHS,
        ),
        ComponentPackage(
            component_id="jre",
            kind="zip",
            display_name="Java runtime",
            source=stage_root / "runtime" / "jre",
            artifact=output_dir / f"DYS-fr-jre-{args.app_version}.zip",
            url=f"{release_base_url}/DYS-fr-jre-{args.app_version}.zip",
            target="_internal/runtime/jre",
            validation_paths=JRE_VALIDATION_PATHS,
        ),
        ComponentPackage(
            component_id="languagetool",
            kind="zip",
            display_name="LanguageTool",
            source=stage_root / "resources" / "languagetool",
            artifact=output_dir / f"DYS-fr-languagetool-{args.app_version}.zip",
            url=f"{release_base_url}/DYS-fr-languagetool-{args.app_version}.zip",
            target="_internal/resources/languagetool",
            validation_paths=LT_VALIDATION_PATHS,
        ),
        ComponentPackage(
            component_id="spacy",
            kind="zip",
            display_name="spaCy French model",
            source=stage_root / "resources" / "spacy" / "models" / "fr_core_news_md",
            artifact=output_dir / f"DYS-fr-spacy-fr_core_news_md-{args.app_version}.zip",
            url=f"{release_base_url}/DYS-fr-spacy-fr_core_news_md-{args.app_version}.zip",
            target="_internal/resources/spacy/models/fr_core_news_md",
            validation_paths=SPACY_VALIDATION_PATHS,
        ),
    ]

    components = [build_zip_component(component) for component in component_specs]

    if args.flavor == "hybrid":
        mistral_source = stage_root / "resources" / "models" / "Mistral-7B-Instruct-v0.3-Q4_K_M.gguf"
        components.append(
            build_file_component(
                ComponentPackage(
                    component_id="mistral",
                    kind="file",
                    display_name="Mistral AI model",
                    source=mistral_source,
                    artifact=None,
                    url=args.mistral_url,
                    target="_internal/resources/models/Mistral-7B-Instruct-v0.3-Q4_K_M.gguf",
                    validation_paths=MISTRAL_VALIDATION_PATHS,
                )
            )
        )

    manifest = build_components_manifest(
        app_version=args.app_version,
        flavor=args.flavor,
        runtime_exe_name=args.runtime_exe_name,
        components=components,
    )
    output_manifest.parent.mkdir(parents=True, exist_ok=True)
    output_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print(f"Component manifest created: {output_manifest}")
    for component in components:
        print(f"{component['id']}: {component['url']} ({component['size']} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STAGE_ROOT = PROJECT_ROOT / "build" / "staging" / "basic"
DEFAULT_MANIFEST = Path(__file__).with_name("assets.manifest.json")
JAVA_VERSION_RE = re.compile(r'version\s+"([^"]+)"')


def load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def ensure_clean_dir(path: Path) -> None:
    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def copy_tree(source: Path, destination: Path) -> None:
    if not source.exists():
        raise FileNotFoundError(f"Missing required source directory: {source}")
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination)


def extract_spacy_model(wheel_path: Path, model_name: str, destination: Path) -> None:
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        with zipfile.ZipFile(wheel_path, "r") as archive:
            archive.extractall(temp_root)

        package_root = temp_root / model_name
        if not package_root.exists():
            raise FileNotFoundError(f"Could not find package root '{model_name}' in {wheel_path}")

        candidates = sorted(
            path
            for path in package_root.glob(f"{model_name}-*")
            if path.is_dir() and (path / "config.cfg").exists()
        )
        if not candidates:
            raise FileNotFoundError(f"Could not locate extracted model directory inside {wheel_path}")

        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(candidates[-1], destination)


def resolve_relative(path_str: str) -> Path:
    path = Path(path_str)
    if path.is_absolute():
        return path
    return PROJECT_ROOT / path


def parse_java_major(version_str: str) -> int | None:
    token = version_str.split("-", 1)[0]
    parts = token.split(".")
    try:
        if parts[0] == "1" and len(parts) > 1:
            return int(parts[1])
        return int(parts[0])
    except ValueError:
        return None


def detect_java_version(java_exe: Path) -> tuple[int | None, str | None, str]:
    proc = subprocess.run(
        [str(java_exe), "-version"],
        capture_output=True,
        text=True,
        check=False,
    )
    output = "\n".join(part for part in [proc.stderr.strip(), proc.stdout.strip()] if part).strip()
    match = JAVA_VERSION_RE.search(output)
    if not match:
        return None, None, output

    detected_version = match.group(1)
    return parse_java_major(detected_version), detected_version, output


def validate_jre_dir(jre_dir: Path, *, minimum_major_version: int | None = None) -> dict[str, object]:
    java_exe = jre_dir / "bin" / ("java.exe" if os.name == "nt" else "java")
    if not java_exe.exists():
        raise FileNotFoundError(f"JRE directory is missing the Java executable: {java_exe}")

    detected_major_version, detected_version, version_output = detect_java_version(java_exe)
    if minimum_major_version is not None and detected_major_version is not None:
        if detected_major_version < minimum_major_version:
            raise RuntimeError(
                f"Embedded JRE major version {detected_major_version} is lower than the required "
                f"minimum {minimum_major_version}: {jre_dir}"
            )

    return {
        "path": jre_dir,
        "java_exe": java_exe,
        "detected_major_version": detected_major_version,
        "detected_version": detected_version,
        "version_output": version_output,
    }


def stage_required_assets(
    manifest: dict,
    *,
    stage_root: Path,
    jre_dir: Path | None,
    include_hybrid: bool,
) -> dict:
    metadata: dict[str, object] = {
        "stage_root": str(stage_root),
        "include_hybrid": include_hybrid,
        "assets": {},
    }

    ensure_clean_dir(stage_root)

    lt_cfg = manifest["languagetool"]
    lt_source = resolve_relative(lt_cfg["source_dir"])
    lt_dest = stage_root / lt_cfg["stage_target"]
    copy_tree(lt_source, lt_dest)
    metadata["assets"]["languagetool"] = {
        "source": str(lt_source),
        "destination": str(lt_dest),
        "version": lt_cfg["version"],
    }

    spacy_cfg = manifest["spacy_model"]
    spacy_dest = stage_root / spacy_cfg["stage_target"]
    extracted_source = resolve_relative(spacy_cfg["source_extracted_dir"])
    if extracted_source.exists():
        copy_tree(extracted_source, spacy_dest)
        spacy_source = extracted_source
        spacy_source_kind = "directory"
    else:
        wheel_parent = resolve_relative(Path(spacy_cfg["source_wheel_glob"]).parent)
        wheel_pattern = Path(spacy_cfg["source_wheel_glob"]).name
        wheels = sorted(wheel_parent.glob(wheel_pattern))
        if not wheels:
            raise FileNotFoundError(
                f"Could not find a spaCy wheel matching '{wheel_pattern}' under {wheel_parent}"
            )
        spacy_source = wheels[-1]
        spacy_source_kind = "wheel"
        extract_spacy_model(spacy_source, spacy_cfg["name"], spacy_dest)

    metadata["assets"]["spacy_model"] = {
        "source": str(spacy_source),
        "source_kind": spacy_source_kind,
        "destination": str(spacy_dest),
        "model": spacy_cfg["name"],
        "version": spacy_cfg["version"],
    }

    jre_cfg = manifest["jre"]
    default_jre = resolve_relative(jre_cfg["default_source"])
    minimum_major_version = jre_cfg.get("minimum_major_version", jre_cfg.get("major_version"))
    resolved_jre = validate_jre_dir(jre_dir or default_jre, minimum_major_version=minimum_major_version)
    jre_dest = stage_root / jre_cfg["stage_target"]
    copy_tree(resolved_jre["path"], jre_dest)
    metadata["assets"]["jre"] = {
        "source": str(resolved_jre["path"]),
        "destination": str(jre_dest),
        "vendor": jre_cfg["vendor"],
        "minimum_major_version": minimum_major_version,
        "detected_major_version": resolved_jre["detected_major_version"],
        "detected_version": resolved_jre["detected_version"],
        "java_exe": str(resolved_jre["java_exe"]),
    }

    mistral_cfg = manifest["mistral"]
    if include_hybrid:
        mistral_source = resolve_relative(mistral_cfg["source"])
        if not mistral_source.exists():
            raise FileNotFoundError(f"Requested hybrid staging but model is missing: {mistral_source}")
        mistral_dest = stage_root / mistral_cfg["stage_target"]
        mistral_dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(mistral_source, mistral_dest)
        metadata["assets"]["mistral"] = {
            "source": str(mistral_source),
            "destination": str(mistral_dest),
        }

    return metadata


def main() -> int:
    parser = argparse.ArgumentParser(description="Stage offline assets for the Windows basic installer.")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST), help="Path to the asset manifest JSON file.")
    parser.add_argument(
        "--stage-root",
        default=str(DEFAULT_STAGE_ROOT),
        help="Directory where the staged runtime payload will be created.",
    )
    parser.add_argument(
        "--jre-dir",
        default=os.getenv("DYS_FR_JRE_DIR", ""),
        help="Path to an embedded JRE root. Falls back to runtime/jre when omitted.",
    )
    parser.add_argument(
        "--include-hybrid",
        action="store_true",
        help="Also stage the optional local Mistral GGUF model.",
    )
    args = parser.parse_args()

    manifest_path = resolve_relative(args.manifest)
    stage_root = resolve_relative(args.stage_root)
    jre_dir = Path(args.jre_dir) if args.jre_dir else None

    manifest = load_manifest(manifest_path)
    metadata = stage_required_assets(
        manifest,
        stage_root=stage_root,
        jre_dir=jre_dir,
        include_hybrid=args.include_hybrid,
    )

    metadata_path = stage_root / "staging-manifest.json"
    metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Staged runtime assets at: {stage_root}")
    print(f"Wrote staging manifest: {metadata_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())


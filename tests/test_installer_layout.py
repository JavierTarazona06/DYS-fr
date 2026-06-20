"""Cross-file invariants between the installer script and the application.

The installer lays files down at paths the application then resolves at runtime, but
nothing connects the two: a rename on either side produces a build that compiles
cleanly and fails on the user's machine. These tests are pure Python and need neither
Windows nor Inno Setup, so the drift fails here instead of during a release.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ISS_PATH = PROJECT_ROOT / "packaging" / "windows" / "installer.iss"
SPEC_PATH = PROJECT_ROOT / "packaging" / "windows" / "dys_fr.spec"
LAUNCHER_PATH = PROJECT_ROOT / "src" / "runtime" / "launcher.py"
CONFIG_PATH = PROJECT_ROOT / "config.yaml"


@pytest.fixture(scope="module")
def iss_text() -> str:
    return ISS_PATH.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def config() -> dict:
    return yaml.safe_load(CONFIG_PATH.read_text(encoding="utf-8"))


def test_installer_exe_name_matches_pyinstaller_spec(iss_text: str) -> None:
    """installer.iss must point at the executable PyInstaller actually emits."""
    spec_names = re.findall(r'name="([^"]+)"', SPEC_PATH.read_text(encoding="utf-8"))
    assert spec_names, "no name= found in dys_fr.spec"
    spec_exe = f"{spec_names[0]}.exe"

    iss_exe = re.search(r'#define\s+AppExe\s+"([^"]+)"', iss_text)
    assert iss_exe, "installer.iss does not define AppExe"
    assert iss_exe.group(1) == spec_exe, (
        f"installer.iss ships {iss_exe.group(1)} but the spec builds {spec_exe}"
    )


def test_app_mutex_matches_launcher(iss_text: str) -> None:
    """A mismatch here silently disables the installer's 'close the app' prompt."""
    iss_mutex = re.search(r'#define\s+AppMutexName\s+"([^"]+)"', iss_text)
    assert iss_mutex, "installer.iss does not define AppMutexName"

    launcher_mutex = re.search(
        r'APP_MUTEX_NAME\s*=\s*"([^"]+)"', LAUNCHER_PATH.read_text(encoding="utf-8-sig")
    )
    assert launcher_mutex, "launcher.py does not define APP_MUTEX_NAME"
    assert iss_mutex.group(1) == launcher_mutex.group(1), (
        "AppMutex in installer.iss and APP_MUTEX_NAME in launcher.py must be identical"
    )


def test_installer_stages_paths_the_config_resolves(iss_text: str, config: dict) -> None:
    """Everything config.yaml points at must be covered by a [Files] destination."""
    destinations = set(re.findall(r'DestDir:\s*"([^"]+)"', iss_text))
    assert destinations, "installer.iss has no [Files] destinations"

    # Runtime paths are resolved relative to {app}\_internal (src/utils/paths.py).
    normalised = {d.replace("{app}\\_internal", "").strip("\\").replace("\\", "/") for d in destinations}

    jar_path = config["lt"]["server"]["jar_path"]
    spacy_dir = config["spacy"]["target_dir"]

    for configured in (jar_path, spacy_dir):
        covered = any(configured.startswith(dest) for dest in normalised if dest)
        assert covered, (
            f"config.yaml points at {configured!r} but no installer.iss DestDir covers it; "
            f"destinations are {sorted(normalised)}"
        )


def test_installer_excludes_the_model_directory(iss_text: str) -> None:
    """The installer channel ships no GGUF: the model is downloaded in-app."""
    assert 'Excludes: "\\models\\*"' in iss_text, (
        "installer.iss must exclude resources\\models; the 4.1 GB model is not shipped"
    )


def test_run_entry_uses_original_user(iss_text: str) -> None:
    """Without runasoriginaluser the first launch writes state to the admin profile."""
    run_section = iss_text.split("[Run]", 1)
    assert len(run_section) == 2, "installer.iss has no [Run] section"
    body = run_section[1].split("[", 1)[0]
    assert "runasoriginaluser" in body, (
        "the [Run] entry must use runasoriginaluser, or the post-install launch runs "
        "elevated and resolves the administrator's %LOCALAPPDATA%"
    )


def test_uninstall_preserves_user_data_by_default(iss_text: str) -> None:
    """The uninstall prompt must default to keeping the ~4 GB model."""
    assert "MB_DEFBUTTON2" in iss_text, (
        "the uninstall confirmation must default to 'Non' so a stray Enter cannot "
        "delete the downloaded model"
    )

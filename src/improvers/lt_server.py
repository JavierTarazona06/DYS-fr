import os, time, subprocess, signal, contextlib, sys, shutil
from pathlib import Path
import urllib.request

class LanguageToolServer(contextlib.AbstractContextManager):
    def __init__(self, host: str, port: int, jre_bin: str, jar_path: str,
                 allow_origin: str = "*", heap_mb: int = 256, lt_args: list[str] | None = None):
        self.host = host
        self.port = int(port)
        self.jre_bin = jre_bin
        self.jar_path = Path(jar_path)
        self.allow_origin = allow_origin
        self.heap_mb = int(heap_mb)
        self.lt_args = lt_args if lt_args is not None else [] # Initialize lt_args
        self.proc: subprocess.Popen | None = None

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def __enter__(self):
        self.start()
        self.wait_healthy(timeout_s=25)
        return self

    def __exit__(self, exc_type, exc, tb):
        self.stop()
        return False

    # ---------- helpers ----------

    def _resolve_java_cmd(self) -> str:
        """
        Resolve the Java executable. If self.jre_bin == "java", use PATH.
        If it's a directory, append /bin/java(.exe). If it’s a file, use it.
        """
        jb = self.jre_bin.strip('"')
        if jb.lower() == "java":
            exe = shutil.which("java")
            if not exe:
                raise RuntimeError(
                    "Could not find 'java' on PATH. Install Java 17+ or set jre_bin to an embedded JRE path."
                )
            return exe

        p = Path(jb)
        if p.is_dir():
            p = p / ("java.exe" if os.name == "nt" else "java")
        return str(p)

    # ---------- lifecycle ----------

    def start(self):
        if not self.jar_path.exists():
            raise FileNotFoundError(
                f"LanguageTool server JAR not found at: {self.jar_path}\n"
                f"Run: python scripts/download_languagetool.py"
            )

        java_cmd = self._resolve_java_cmd()

        args = [
            java_cmd,
            f"-Xmx{self.heap_mb}m",
            "-jar", str(self.jar_path),
            "--port", str(self.port),
            "--allow-origin", self.allow_origin,
        ] + self.lt_args # Append custom LanguageTool arguments

        env = os.environ.copy()
        # Only set JAVA_HOME if using an embedded JRE path (not when jre_bin == "java")
        if self.jre_bin.lower() != "java":
            try:
                jp = Path(java_cmd).resolve()
                # .../jre/bin/java(.exe) -> JAVA_HOME = parent of 'bin'
                env["JAVA_HOME"] = str(jp.parent.parent)
            except Exception:
                # Not critical; server will still run if java_cmd is valid
                pass

        creationflags = 0
        if os.name == "nt":
            # Create a new process group so we can terminate cleanly on Windows
            creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)

        print(f"Starting LanguageTool server: {' '.join(args)}")

        # Inherit stdout/stderr so we don't block on a full pipe if LT logs a lot
        self.proc = subprocess.Popen(
            args,
            stdout=None,
            stderr=None,
            env=env,
            creationflags=creationflags,
        )

    def wait_healthy(self, timeout_s: float = 25):
        url = f"{self.url}/v2/languages"
        t0 = time.time()
        last_err = None
        while time.time() - t0 < timeout_s:
            try:
                with urllib.request.urlopen(url, timeout=2) as r:
                    if r.status == 200:
                        return
            except Exception as e:
                last_err = e
            time.sleep(0.3)
        raise RuntimeError(f"LanguageTool server not healthy at {url}: {last_err}")

    def stop(self):
        if self.proc and self.proc.poll() is None:
            try:
                if os.name == "nt":
                    # On Windows, use taskkill to force termination
                    subprocess.run(
                        ["taskkill", "/F", "/T", "/PID", str(self.proc.pid)],
                        capture_output=True,
                        check=False
                    )
                else:
                    self.proc.terminate()
                
                # Wait for process to end
                try:
                    self.proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    # Force kill if still running
                    self.proc.kill()
            except Exception:
                try:
                    self.proc.kill()
                except Exception:
                    pass
        self.proc = None
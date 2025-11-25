import subprocess, sys, os
from pathlib import Path
from src.utils.config import load_config
from src.improvers.lt_server import LanguageToolServer

def main():
    cfg = load_config()
    lt_cfg = cfg["lt"]["server"]
    host, port = lt_cfg["host"], int(lt_cfg["port"])

    # Start LT server (embedded JRE + JAR)
    with LanguageToolServer(
        host=host, port=port,
        jre_bin=lt_cfg["jre_bin"],
        jar_path=lt_cfg["jar_path"],
        allow_origin=lt_cfg.get("allow_origin", "*"),
        heap_mb=int(lt_cfg.get("heap_mb", 256)),
        lt_args=[] # Remove config argument - not needed
    ) as srv:
        env = os.environ.copy()
        env["LT_URL"] = srv.url
        env["LT_LANG"] = cfg["lt"]["lang"]

        # Launch Streamlit UI
        streamlit_cmd = [sys.executable, "-m", "streamlit", "run", "app.py", "--server.port=8501"]
        ui = subprocess.Popen(streamlit_cmd, env=env)
        try:
            ui.wait()
        finally:
            try:
                ui.terminate()
            except Exception:
                pass

if __name__ == "__main__":
    main()
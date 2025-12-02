import subprocess, sys, os
from pathlib import Path
from src.utils.config import load_config

# Import shared LT server initialization
sys.path.insert(0, str(Path(__file__).parent))
from scripts.start_lt_server import start_lt_server_from_config


def main():
    cfg = load_config()

    # Start LT server using shared configuration
    with start_lt_server_from_config() as srv:
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
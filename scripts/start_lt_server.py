"""
Standalone script to start only the LanguageTool server.
Used by test suites to avoid launching Streamlit UI.
Shares the exact same server configuration as runner.py.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.config import load_config
from src.improvers.lt_server import LanguageToolServer


def start_lt_server_from_config():
    """
    Start LanguageTool server using configuration from config.yaml.
    Returns the LanguageToolServer context manager.
    This function is shared between runner.py and start_lt_server.py
    to ensure identical server configuration.
    """
    cfg = load_config()
    lt_cfg = cfg["lt"]["server"]
    host, port = lt_cfg["host"], int(lt_cfg["port"])
    
    return LanguageToolServer(
        host=host,
        port=port,
        jre_bin=lt_cfg["jre_bin"],
        jar_path=lt_cfg["jar_path"],
        allow_origin=lt_cfg.get("allow_origin", "*"),
        heap_mb=int(lt_cfg.get("heap_mb", 256)),
        lt_args=lt_cfg.get("lt_args", [])  # Support custom args from config
    )


def main():
    """Start LanguageTool server and keep it running."""
    cfg = load_config()
    lt_cfg = cfg["lt"]["server"]
    host, port = lt_cfg["host"], int(lt_cfg["port"])

    print(f"Starting LanguageTool server at http://{host}:{port}")
    print("Press Ctrl+C to stop the server...\n")

    # Use shared server initialization
    with start_lt_server_from_config() as srv:
        print(f"✓ LanguageTool server ready at {srv.url}")
        print("Server is running. Press Ctrl+C to stop.\n")
        
        try:
            # Keep server alive
            srv._proc.wait()
        except KeyboardInterrupt:
            print("\n\nShutting down LanguageTool server...")


if __name__ == "__main__":
    main()

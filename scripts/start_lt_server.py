"""
Standalone script to start only the LanguageTool server.
Used by test suites to avoid launching Streamlit UI.
Shares the exact same server configuration as runner.py.
"""
import sys
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.config import load_config
from src.improvers.lt_server import LanguageToolServer


def check_port_in_use(port: int) -> int | None:
    """
    Check if a port is in use and return the PID using it.
    Returns None if port is free.
    """
    try:
        result = subprocess.run(
            ["netstat", "-ano"],
            capture_output=True,
            text=True,
            check=True
        )
        
        for line in result.stdout.splitlines():
            if f":{port}" in line and "LISTENING" in line:
                parts = line.split()
                pid = parts[-1]
                if pid.isdigit():
                    return int(pid)
        return None
    except Exception:
        return None


def kill_process(pid: int) -> bool:
    """Kill a process by PID. Returns True if successful."""
    try:
        subprocess.run(["taskkill", "/F", "/PID", str(pid)], check=True, capture_output=True)
        return True
    except Exception:
        return False


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

    # Check if port is already in use
    existing_pid = check_port_in_use(port)
    if existing_pid:
        print(f"⚠️  Port {port} is already in use by process {existing_pid}")
        print(f"Attempting to terminate process {existing_pid}...")
        if kill_process(existing_pid):
            print(f"✓ Process {existing_pid} terminated successfully")
            import time
            time.sleep(1)  # Wait for port to be released
        else:
            print(f"✗ Failed to terminate process {existing_pid}")
            print(f"Please manually close the process or use a different port")
            return 1

    print(f"Starting LanguageTool server at http://{host}:{port}")
    print("Press Ctrl+C to stop the server...\n")

    # Use shared server initialization
    with start_lt_server_from_config() as srv:
        print(f"✓ LanguageTool server ready at {srv.url}")
        print("Server is running. Press Ctrl+C to stop.\n")
        
        try:
            # Keep server alive indefinitely (Windows-compatible)
            import time
            while True:
                if srv.proc and srv.proc.poll() is not None:
                    # Process died unexpectedly - show output
                    print(f"\n⚠️  Server process exited with code: {srv.proc.returncode}")
                    print("\nServer output:")
                    print("="*70)
                    if srv.proc.stdout:
                        output = srv.proc.stdout.read()
                        if output:
                            print(output.decode('utf-8', errors='replace'))
                    print("="*70)
                    break
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n\nShutting down LanguageTool server...")
    
    return 0


if __name__ == "__main__":
    main()

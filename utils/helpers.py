"""
Shared test utilities for test suites.
"""
import requests
from src.utils.config import load_config


def ensure_lt_server_running():
    """
    Verify that LanguageTool server is running.
    
    Returns:
        str: Server URL if running
        
    Raises:
        ConnectionError: If server is not running
    """
    cfg = load_config()
    server_url = f"http://{cfg['lt']['server']['host']}:{cfg['lt']['server']['port']}"
    
    try:
        response = requests.get(f"{server_url}/v2/languages", timeout=2)
        if response.status_code == 200:
            return server_url
    except:
        pass
    
    raise ConnectionError(
        f"LanguageTool server not running at {server_url}\n"
        f"Start it manually in a separate terminal:\n"
        f"  python scripts/start_lt_server.py"
    )

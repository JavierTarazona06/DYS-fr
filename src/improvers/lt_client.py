from language_tool_python import LanguageTool
from language_tool_python.utils import correct
import requests

class LTClient:
    """Thin wrapper around language_tool_python client in remote mode."""
    def __init__(self, lang: str, server_url: str, *, config: dict | None = None):
        # Verify server is responding before creating client
        try:
            response = requests.get(f"{server_url}/v2/languages", timeout=5)
            if response.status_code != 200:
                raise ConnectionError(f"LanguageTool server returned status {response.status_code}")
        except requests.exceptions.Timeout:
            raise ConnectionError(f"LanguageTool server timeout at {server_url}")
        except requests.exceptions.RequestException as e:
            raise ConnectionError(f"Cannot connect to LanguageTool server at {server_url}: {e}")
        
        self.tool = LanguageTool(lang, remote_server=server_url)

    def check(self, text: str):
        return self.tool.check(text)

    def correct_raw(self, text: str) -> str:
        return correct(text, self.check(text))

    def close(self):
        self.tool.close()
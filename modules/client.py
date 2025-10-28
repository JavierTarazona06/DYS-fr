from language_tool_python import LanguageTool
from language_tool_python.utils import correct

class LTClient:
    """Tiny wrapper around language_tool_python client in remote mode."""
    def __init__(self, lang: str, server_url: str):
        self.tool = LanguageTool(lang, remote_server=server_url)

    def check(self, text: str):
        return self.tool.check(text)

    def correct(self, text: str) -> str:
        return correct(text, self.check(text))

    def close(self):
        self.tool.close()

import os

# Defaults (can be overridden by env vars)
DEFAULT_PORT = int(os.getenv("LT_PORT", "8085"))
DEFAULT_LANG = os.getenv("LT_LANG", "en-US")
HEALTH_TIMEOUT_S = float(os.getenv("LT_HEALTH_TIMEOUT", "20"))
ALLOW_ORIGIN = os.getenv("LT_ALLOW_ORIGIN", "*")


# https://internal1.languagetool.org/snapshots/LanguageTool-latest-snapshot.zip
import time, requests
from .config import HEALTH_TIMEOUT_S

def wait_until_ready(base_url: str, timeout_s: float = HEALTH_TIMEOUT_S) -> None:
    """Poll /v2/languages until the LT server is ready."""
    t0 = time.time()
    url = f"{base_url.rstrip('/')}/v2/languages"
    while time.time() - t0 < timeout_s:
        try:
            r = requests.get(url, timeout=0.5)
            if r.ok:
                return
        except requests.RequestException:
            pass
        time.sleep(0.2)
    raise RuntimeError("LanguageTool server did not become ready in time")

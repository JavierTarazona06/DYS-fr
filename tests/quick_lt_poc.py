from src.improvers.lt_improver import LTImprover
from src.utils.config import load_config
from utils.test_helpers import ensure_lt_server_running

TEXT = "Departement of meeddicine Colombia University closed on August 1 Milinda Samuelli"

def main():
    """Quick proof-of-concept for LanguageTool correction."""
    # Verify server is running
    server_url = ensure_lt_server_running()
    
    cfg = load_config()
    imp = LTImprover(cfg["lt"]["lang"], server_url)
    
    print("Original:")
    print(TEXT)
    print("\nCorrected:")
    print(imp.improve(TEXT))
    
    imp.close()

if __name__ == "__main__":
    main()

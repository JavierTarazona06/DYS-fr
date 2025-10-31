from src.improvers.lt_server import LanguageToolServer
from src.improvers.lt_improver import LTImprover
from src.utils.config import load_config

TEXT = "Departement of meeddicine Colombia University closed on August 1 Milinda Samuelli"

def main():
    cfg = load_config()
    ltc = cfg["lt"]
    srv = ltc["server"]
    with LanguageToolServer(srv["host"], srv["port"], srv["jre_bin"], srv["jar_path"]) as s:
        imp = LTImprover(ltc["lang"], s.url)
        print(TEXT)
        print(imp.improve(TEXT))
        imp.close()

if __name__ == "__main__":
    main()

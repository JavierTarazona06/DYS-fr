from modules.server import LanguageToolServer
from modules.client import LTClient
from modules.config import DEFAULT_LANG, DEFAULT_PORT

TEXT = "Departement of meeddicine Colombia University closed on August 1 Milinda Samuelli"

def main():
    with LanguageToolServer(port=DEFAULT_PORT) as srv:
        lt = LTClient(DEFAULT_LANG, srv.url)
        try:
            print(TEXT)
            print(lt.correct(TEXT))
        finally:
            lt.close()

if __name__ == "__main__":
    main()

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.config import load_config
from src.guardrails.spacy_loader import load_french_nlp
from src.guardrails.entities import mask_entities, reinject_entities
from src.improvers.lt_improver import LTImprover

TEXT = "Ce juor, le 12 janvier 2024, Marie Dampan ont visité Paris."
# Je suis allé au supermarché pour achète du pin et des lais, mets la caissière à fermer la caisse à 18h et j'ai dû rentrer sans rien.


def main() -> None:
    cfg = load_config()
    spacy_cfg = cfg["spacy"]
    lt_cfg = cfg["lt"]
    srv_cfg = lt_cfg["server"]

    nlp = load_french_nlp(
        spacy_cfg["model"],
        only_ner_pos=spacy_cfg["only_ner_pos"],
        add_date_ruler=spacy_cfg.get("add_date_ruler", False),
    )
    doc = nlp(TEXT)
    masked_txt, masked = mask_entities(doc)

    print("Input:")
    print(TEXT)
    print("\nMasked text:")
    print(masked_txt)
    print("\nMasked entities:")
    for m in masked:
        print(m)

    server_url = f"http://{srv_cfg['host']}:{srv_cfg['port']}"
    improver = LTImprover(lt_cfg["lang"], server_url)
    improved = improver.improve(masked_txt)
    improver.close()

    final = reinject_entities(improved, masked)

    print("\nImproved (LanguageTool):")
    print(improved)
    print("\nFinal with entities:")
    print(final)


if __name__ == "__main__":
    main()



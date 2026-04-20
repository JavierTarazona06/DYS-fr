import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.utils.config import load_config

from src.guardrails.spacy_loader import load_french_nlp
from src.guardrails.entities import mask_entities, reinject_entities

cfg = load_config()
spacy = cfg["spacy"]

nlp = load_french_nlp(
    spacy["model"],
    only_ner_pos=spacy["only_ner_pos"],
    add_date_ruler=spacy.get("add_date_ruler", False),
)
txt = "Ce jour, le 12 janvier 2024, Marie Dubois a visité Paris."
print(f"\ntxt:\n{txt}")
doc = nlp(txt)
masked_txt, masked = mask_entities(doc)

print("\nmasked_txt:")
print(masked_txt)
print("\nmasked:")
print(masked)

# -> pasa masked_txt a tu corrector/reglas/LLM
# ... obtener 'improved'

improved = masked_txt  # demo: sin cambios
final = reinject_entities(improved, masked)
print("\nfinal:")
print(final)
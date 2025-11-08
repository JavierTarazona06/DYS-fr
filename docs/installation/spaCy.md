# SpaCy Installation

1) Crear entorno e instalar spaCy 3.8

# Windows / Linux / macOS
python -m venv .venv
# Win
.\.venv\Scripts\activate
# Linux/Mac
source .venv/bin/activate

pip install -r requirements.txt

2) Instalar el modelo francés (2 rutas)

Ruta  (determinística/offline para empaquetar)

Obtén la URL exacta del wheel compatible con tu spaCy (--url):

python -m spacy info fr_core_news_md --url

Descarga ese .whl y añádelo a tu repo (p. ej., resources/spacy/fr_core_news_md.whl)
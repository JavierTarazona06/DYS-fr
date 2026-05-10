Para correr **Mistral-7B-Instruct v0.3** localmente en **CPU con ≤4 GB RAM** usando cuantización de **4 bits** e integrarlo al proyecto, aquí está la guía completa:

---

## 🎯 **Opción recomendada: llama.cpp**

### **1. Descargar el modelo cuantizado (Q4_K_M)** 

Read [](file:///c%3A/Users/javit/Documents/ENSTA/EngagementCitoyen/DYS-fr/README.md)

El modelo **Mistral-7B-Instruct v0.3** cuantizado a **Q4_K_M** (~4 GB) está disponible en Hugging Face:

```bash
# URL del modelo cuantizado
https://huggingface.co/TheBloke/Mistral-7B-Instruct-v0.3-GGUF
```

**Archivo específico a descargar:**
```
mistral-7b-instruct-v0.3.Q4_K_M.gguf  (~4.37 GB)
```

### **2. Estructura de carpetas**

Según tu documentación, el modelo debe ir en:

```
resources/
  models/
    mistral-7b-instruct-v0.3.Q4_K_M.gguf
```

### **3. Instalar llama-cpp-python**

Agrega a requirements.txt:

```txt
llama-cpp-python>=0.2.0
```

O instala directamente:

```bash
pip install llama-cpp-python
```

**Para CPU con optimizaciones AVX2/AVX512:**
```bash
CMAKE_ARGS="-DLLAMA_BLAS=ON -DLLAMA_BLAS_VENDOR=OpenBLAS" pip install llama-cpp-python
```

### **4. Crear el componente LLM Improver**

Crea el archivo `src/improvers/llm_improver.py`:

```python
from __future__ import annotations
import os
from typing import Optional

from llama_cpp import Llama
from spacy.language import Language

from src.guardrails.entities import mask_entities, reinject_entities
from .base import TextImprover
from .lt_client import LTClient

class LLMImprover(TextImprover):
    """
    Hybrid improver: uses LanguageTool for pre-pass, then LLM for rewriting,
    followed by post-validation.
    """
    
    def __init__(
        self,
        model_path: str,
        lang: str,
        lt_server_url: str,
        nlp: Language | None = None,
        n_ctx: int = 4096,
        n_threads: int | None = None,
        max_tokens: int = 512,
        temperature: float = 0.3,
    ):
        """
        :param model_path: Path to the GGUF model file
        :param lang: Language code for LanguageTool ("fr")
        :param lt_server_url: LanguageTool server URL
        :param nlp: spaCy model for NER
        :param n_ctx: Context window size (default 4096)
        :param n_threads: Number of CPU threads (None = auto-detect)
        :param max_tokens: Max tokens to generate
        :param temperature: Sampling temperature (lower = more deterministic)
        """
        self.nlp = nlp
        self.lt_client = LTClient(lang, lt_server_url)
        self.max_tokens = max_tokens
        self.temperature = temperature
        
        # Load LLM with CPU-optimized settings
        self.llm = Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            n_threads=n_threads or os.cpu_count(),
            n_gpu_layers=0,  # CPU only
            use_mlock=True,  # Keep model in RAM
            verbose=False,
        )
    
    def _build_prompt(self, text: str, lt_hints: list[str]) -> str:
        """Build instruction prompt for Mistral."""
        hints_str = "\n".join(f"- {h}" for h in lt_hints) if lt_hints else "Aucune erreur détectée."
        
        return f"""<s>[INST] Tu es un assistant qui corrige et clarifie le texte français SANS AJOUTER d'informations nouvelles.

Règles strictes:
1. Ne modifie JAMAIS les marqueurs ENT_X_Y
2. Ne change JAMAIS les nombres, dates ou noms propres
3. N'ajoute AUCUNE information manquante (laisse les "..." et "..")
4. Corrige uniquement la grammaire, orthographe et ponctuation
5. Simplifie les phrases trop longues si possible

Erreurs détectées par LanguageTool:
{hints_str}

Texte à corriger:
{text}

Texte corrigé: [/INST]"""
    
    def _extract_lt_hints(self, matches) -> list[str]:
        """Extract error messages from LanguageTool matches."""
        hints = []
        for m in matches[:5]:  # Limit to top 5 errors
            msg = getattr(m, 'message', '')
            if msg:
                hints.append(msg)
        return hints
    
    def _count_lt_errors(self, text: str) -> int:
        """Count errors detected by LanguageTool."""
        matches = self.lt_client.check(text)
        return len(matches)
    
    def improve(self, text: str) -> str:
        """
        Hybrid pipeline:
        1. Mask entities (spaCy)
        2. Pre-pass with LT (get hints + initial correction)
        3. LLM rewrite with constraints
        4. Post-validation (degrade if LT errors increase)
        5. Reinject entities
        """
        masked = []
        text_to_check = text
        
        # Step 1: Mask entities
        if self.nlp is not None:
            doc = self.nlp(text)
            text_to_check, masked = mask_entities(doc)
        
        # Step 2: Pre-pass with LT
        lt_matches_before = self.lt_client.check(text_to_check)
        error_count_before = len(lt_matches_before)
        lt_hints = self._extract_lt_hints(lt_matches_before)
        
        # Step 3: LLM rewrite
        prompt = self._build_prompt(text_to_check, lt_hints)
        
        try:
            response = self.llm(
                prompt,
                max_tokens=self.max_tokens,
                temperature=self.temperature,
                stop=["</s>", "[INST]"],
                echo=False,
            )
            llm_output = response['choices'][0]['text'].strip()
        except Exception as e:
            print(f"[LLM_ERROR] {e}")
            # Fallback: return original text
            return reinject_entities(text_to_check, masked) if masked else text
        
        # Step 4: Post-validation
        error_count_after = self._count_lt_errors(llm_output)
        
        if error_count_after > error_count_before:
            print(f"[LLM_DEGRADED] Errors increased ({error_count_before} → {error_count_after}), reverting to input")
            final_text = text_to_check
        else:
            final_text = llm_output
        
        # Step 5: Reinject entities
        if masked:
            final_text = reinject_entities(final_text, masked)
        
        return final_text
    
    def close(self):
        """Release resources."""
        self.lt_client.close()
        # llama-cpp-python handles cleanup automatically
```

### **5. Configuración en config.yaml** 

Read [](file:///c%3A/Users/javit/Documents/ENSTA/EngagementCitoyen/DYS-fr/config.yaml)

Actualiza config.yaml para incluir configuración del LLM:

```yaml
# Modo: "lt" (solo reglas) o "hybrid" (LT + LLM)
improver: lt

lt:
  lang: fr
  server:
    host: 127.0.0.1
    port: 8081
    jar_path: resources/languagetool/languagetool-server.jar
    jre_bin: java
    allow_origin: "*"
    heap_mb: 256

llm:
  # Modelo a usar: "mistral-7b-q4" o "gemma3-4b"
  model: mistral-7b-q4
  models_dir: resources/models
  
  mistral:
    filename: mistral-7b-instruct-v0.3.Q4_K_M.gguf
    n_ctx: 4096
    max_tokens: 512
    temperature: 0.3
    
  gemma:
    filename: gemma-3-4b-instruct-Q4_K_M.gguf
    n_ctx: 4096
    max_tokens: 512
    temperature: 0.3

spacy:
  model: fr_core_news_md
  only_ner_pos: true
  target_dir: resources/spacy
  add_date_ruler: true
```

### **6. Script de descarga automática**

Crea `scripts/download_mistral.py`:

```python
#!/usr/bin/env python3
"""Download Mistral-7B-Instruct v0.3 Q4_K_M model from Hugging Face."""

import os
from pathlib import Path
from huggingface_hub import hf_hub_download

REPO_ID = "TheBloke/Mistral-7B-Instruct-v0.3-GGUF"
FILENAME = "mistral-7b-instruct-v0.3.Q4_K_M.gguf"
LOCAL_DIR = Path(__file__).parent.parent / "resources" / "models"

def download_model():
    LOCAL_DIR.mkdir(parents=True, exist_ok=True)
    
    model_path = LOCAL_DIR / FILENAME
    if model_path.exists():
        print(f"✓ Model already exists: {model_path}")
        return str(model_path)
    
    print(f"Downloading {FILENAME} from {REPO_ID}...")
    print(f"This will download ~4.37 GB")
    
    downloaded_path = hf_hub_download(
        repo_id=REPO_ID,
        filename=FILENAME,
        local_dir=LOCAL_DIR,
        local_dir_use_symlinks=False,
    )
    
    print(f"✓ Model downloaded: {downloaded_path}")
    return downloaded_path

if __name__ == "__main__":
    download_model()
```

Agrega a requirements.txt:
```txt
huggingface-hub>=0.20.0
```

### **7. Integración en app.py (Streamlit)**

```python
import streamlit as st
import yaml
from pathlib import Path

from src.improvers.lt_improver import LTImprover
from src.improvers.llm_improver import LLMImprover
from src.guardrails.spacy_loader import load_french_nlp

# Load config
with open("config.yaml") as f:
    config = yaml.safe_load(f)

# Load spaCy
nlp = load_french_nlp(
    config['spacy']['model'],
    only_ner_pos=config['spacy']['only_ner_pos'],
    add_date_ruler=config['spacy']['add_date_ruler'],
)

# Mode selector
mode = st.sidebar.selectbox(
    "Mode de correction",
    ["Léger (règles)", "Intelligent (hybride)"],
    index=0,
)

# Initialize improver
if mode == "Léger (règles)":
    improver = LTImprover(
        lang=config['lt']['lang'],
        server_url=f"http://{config['lt']['server']['host']}:{config['lt']['server']['port']}",
        nlp=nlp,
    )
else:
    # Hybrid mode with LLM
    model_name = config['llm']['model']
    model_config = config['llm'][model_name.replace('-q4', '')]
    model_path = Path(config['llm']['models_dir']) / model_config['filename']
    
    if not model_path.exists():
        st.error(f"Modèle introuvable: {model_path}")
        st.info("Exécutez: `python scripts/download_mistral.py`")
        st.stop()
    
    with st.spinner("Chargement du modèle LLM..."):
        improver = LLMImprover(
            model_path=str(model_path),
            lang=config['lt']['lang'],
            lt_server_url=f"http://{config['lt']['server']['host']}:{config['lt']['server']['port']}",
            nlp=nlp,
            n_ctx=model_config['n_ctx'],
            max_tokens=model_config['max_tokens'],
            temperature=model_config['temperature'],
        )

# UI
st.title("🔤 DYS-fr - Correcteur de texte français")

input_text = st.text_area("Texte à corriger", height=200)

if st.button("Corriger"):
    if input_text.strip():
        with st.spinner("Correction en cours..."):
            output_text = improver.improve(input_text)
        
        st.subheader("Texte corrigé")
        st.write(output_text)
    else:
        st.warning("Veuillez entrer du texte")
```

### **8. Uso de memoria**

**Requisitos para Mistral-7B Q4_K_M:**
- Modelo: ~4.37 GB
- Context window (4096 tokens): ~0.5 GB
- Overhead Python/llama.cpp: ~0.5 GB
- **Total: ~5.5-6 GB RAM**

**Si tienes solo 4 GB:**
- Reduce `n_ctx` a 2048: ahorra ~0.25 GB
- Usa `use_mmap=True` en Llama (swap a disco si necesario)
- Considera **Gemma 3 4B** (~2.5 GB) en su lugar

### **9. Optimizaciones CPU**

```python
# En LLMImprover.__init__()
self.llm = Llama(
    model_path=model_path,
    n_ctx=2048,  # Reducir si RAM limitada
    n_threads=4,  # Ajustar según CPU (más threads = más rápido)
    n_batch=512,  # Batch size (más bajo = menos RAM)
    use_mlock=False,  # Deshabilitar si RAM < 6 GB
    use_mmap=True,  # Usar memory mapping (más lento, menos RAM)
    n_gpu_layers=0,  # CPU only
    verbose=False,
)
```

### **10. Script de prueba**

Crea `scripts/test_mistral.py`:

```python
from pathlib import Path
from llama_cpp import Llama

model_path = Path("resources/models/mistral-7b-instruct-v0.3.Q4_K_M.gguf")

if not model_path.exists():
    print(f"Error: {model_path} no encontrado")
    print("Ejecuta: python scripts/download_mistral.py")
    exit(1)

print("Cargando modelo...")
llm = Llama(
    model_path=str(model_path),
    n_ctx=2048,
    n_threads=4,
    n_gpu_layers=0,
    verbose=True,
)

prompt = """<s>[INST] Corrige este texto francés sin agregar información:

"Je mange un pomme a Paris en 2024"

Texto corrigido: [/INST]"""

print("\nGenerando respuesta...")
response = llm(prompt, max_tokens=100, temperature=0.3)
print("\nRespuesta:")
print(response['choices'][0]['text'])
```

---

## 📊 **Resumen de pasos**

1. ✅ Instalar `llama-cpp-python`
2. ✅ Descargar modelo: `python scripts/download_mistral.py`
3. ✅ Crear `src/improvers/llm_improver.py`
4. ✅ Actualizar config.yaml
5. ✅ Integrar en app.py
6. ✅ Probar: `python scripts/test_mistral.py`

**Memoria necesaria:** ~5.5-6 GB RAM (o ~4 GB con `n_ctx=2048`)

¿Quieres que implemente alguna de estas partes?
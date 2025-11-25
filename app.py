import os
import streamlit as st
from pathlib import Path
from src.utils.config import load_config
from src.guardrails.spacy_loader import load_french_nlp
from src.improvers.lt_improver import LTImprover
from src.improvers.llm_improver import LLMImprover

st.set_page_config(page_title="DYS-fr - Correcteur de texte français", layout="wide")

cfg = load_config()
server_url = os.getenv("LT_URL", f"http://{cfg['lt']['server']['host']}:{cfg['lt']['server']['port']}")
lang = os.getenv("LT_LANG", cfg["lt"]["lang"])

@st.cache_resource
def _get_nlp():
    spacy_cfg = cfg["spacy"]
    return load_french_nlp(
        spacy_cfg["model"],
        only_ner_pos=spacy_cfg.get("only_ner_pos", True),
        add_date_ruler=spacy_cfg.get("add_date_ruler", False),
    )

@st.cache_resource
def _get_lt_improver():
    nlp = _get_nlp()
    return LTImprover(lang=lang, server_url=server_url, nlp=nlp)

@st.cache_resource
def _get_llm_improver():
    nlp = _get_nlp()
    
    # Get model configuration
    model_name = cfg['llm']['model']
    # Extract base name (e.g., "mistral-7b-q4" -> "mistral")
    base_name = model_name.replace('-7b-q4', '').replace('-q4', '')
    model_config = cfg['llm'][base_name]
    
    # Build model path
    model_path = Path(cfg['llm']['models_dir']) / model_config['filename']
    
    if not model_path.exists():
        raise FileNotFoundError(f"Model not found: {model_path}")
    
    return LLMImprover(
        model_path=str(model_path),
        lang=lang,
        lt_server_url=server_url,
        nlp=nlp,
        n_ctx=model_config['n_ctx'],
        max_tokens=model_config['max_tokens'],
        temperature=model_config['temperature'],
    )

# Sidebar: Mode selector
st.sidebar.title("⚙️ Configuration")
mode = st.sidebar.selectbox(
    "Mode de correction",
    ["Léger (règles)", "Intelligent (hybride)"],
    index=0,
    help="Léger: correction rapide avec LanguageTool uniquement\nIntelligent: utilise Mistral-7B pour amélioration contextuelle"
)

# Main UI
st.title("🔤 DYS-fr - Correcteur de texte français")
st.markdown("*Assistant de correction pour personnes dyslexiques*")

# Initialize improver based on mode
if mode == "Léger (règles)":
    improver = _get_lt_improver()
    st.sidebar.success("✓ Mode LanguageTool actif")
else:
    # Hybrid mode with LLM
    try:
        with st.spinner("⏳ Chargement du modèle Mistral-7B (peut prendre 10-30 secondes)..."):
            improver = _get_llm_improver()
        st.sidebar.success("✓ Mode hybride (LT + Mistral) actif")
    except FileNotFoundError as e:
        st.sidebar.error("❌ Modèle Mistral non trouvé")
        st.error(f"**Erreur:** {e}")
        st.info("""
        **Pour installer le modèle Mistral:**
        
        1. Installez llama-cpp-python:
        ```bash
        pip install llama-cpp-python --prefer-binary
        ```
        
        2. Téléchargez le modèle:
        ```bash
        python scripts/download_mistral.py
        ```
        
        3. Redémarrez l'application
        """)
        st.stop()
    except Exception as e:
        st.sidebar.error("❌ Erreur de chargement du modèle")
        st.error(f"**Erreur:** {e}")
        st.stop()

# Input text area
text = st.text_area(
    "Texte à corriger",
    height=220,
    value="Je sui aller au supermarchet pour achète du pin et du lais, mes la caissiere a fermer la caise a 18h et jai dus rentré sans rien.",
    help="Entrez le texte à corriger (avec fautes d'orthographe, de grammaire, etc.)"
)

# Correction button
if st.button("✨Corriger", type="primary"):
    if text.strip():
        with st.spinner("🔄 Correction en cours..."):
            # Enable debug mode for hybrid improver
            if mode == "Intelligent (hybride)":
                out = improver.improve(text, debug=False)
            else:
                out = improver.improve(text)
        
        st.subheader("📝 Texte corrigé")
        st.success(out)
        
        # Show diff in expander
        with st.expander("📊 Voir les différences"):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Avant:**")
                st.code(text, language=None)
            with col2:
                st.markdown("**Après:**")
                st.code(out, language=None)
    else:
        st.warning("⚠️ Veuillez entrer du texte à corriger")

# Sidebar info
st.sidebar.markdown("---")
st.sidebar.markdown("""
### 📖 À propos

**DYS-fr** est un correcteur de texte français optimisé pour les personnes dyslexiques.

**Modes disponibles:**
- **Léger:** Corrections grammaticales rapides (LanguageTool)
- **Intelligent:** Reformulations contextuelles (Mistral-7B + LanguageTool)

**Protection des données sensibles:**
- Les noms propres sont préservés
- Les dates et entités sont protégées
- Traitement 100% local (offline)
""")

# Streamlit will keep the resource alive; optional cleanup on stop not needed here.

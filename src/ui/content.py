# src/ui/content.py

class Content:
    APP_TITLE = "🔤 DYS-fr - Correcteur de texte français"
    APP_SUBTITLE = "*Assistant de correction pour personnes dyslexiques*"
    
    # Sidebar
    SIDEBAR_TITLE = "⚙️ Configuration"
    MODE_LABEL = "Mode de correction"
    MODE_LIGHT = "Léger (règles)"
    MODE_HYBRID = "Intelligent (IA locale)"
    
    MODE_HELP = (
        "Léger: correction rapide avec LanguageTool uniquement\n"
        "Intelligent: reformulations contextuelles avec IA"
    )
    
    ABOUT_TITLE = "### 📖 À propos"
    ABOUT_TEXT = """
    **DYS-fr** est un correcteur de texte français optimisé pour les personnes dyslexiques.
    
    **Protection des données sensibles:**
    - Les noms propres sont préservés
    - Les dates et entités sont protégées
    - Traitement 100% local (offline)
    """

    # Main UI
    INPUT_LABEL = "Texte à corriger"
    INPUT_PLACEHOLDER = "Je sui aller au supermarchet..."
    INPUT_HELP = "Entrez le texte à corriger."
    
    BTN_CORRECT = "✨ Corriger"
    SECTION_RESULT = "📝 Texte corrigé"
    SECTION_DIFF = "📊 Voir les différences"
    
    # Errors/Status
    ERR_NO_TEXT = "⚠️ Veuillez entrer du texte à corriger"
    ERR_MODEL_NOT_FOUND = "❌ Modèle IA introuvable"
    
    @staticmethod
    def install_instructions(model_name: str) -> str:
        return f"""
        **Pour installer le modèle {model_name}:**
        1. `pip install llama-cpp-python --prefer-binary`
        2. Assurez-vous que le fichier `.gguf` est dans `resources/models/`
        3. Redémarrez l'application
        """
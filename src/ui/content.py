# src/ui/content.py


class Content:
    APP_TITLE = "DYS-fr - Correcteur de texte français"
    APP_SUBTITLE = "*Assistant de correction pour personnes dyslexiques*"

    SIDEBAR_TITLE = "Configuration"
    MODE_LABEL = "Mode de correction"
    MODE_LIGHT = "Léger (règles)"
    MODE_HYBRID = "Intelligent (IA locale)"
    MODEL_LABEL = "Modèle IA"

    MODE_HELP = (
        "Léger: correction rapide avec LanguageTool uniquement\n"
        "Intelligent: reformulations contextuelles avec IA"
    )
    MODEL_HELP = "Les modèles IA n'apparaissent que si leur runtime est disponible."
    HYBRID_UNAVAILABLE = "Le mode IA n'est pas disponible dans cette installation."

    ABOUT_TITLE = "### À propos"
    ABOUT_TEXT = """
    **DYS-fr** est un correcteur de texte français optimisé pour les personnes dyslexiques.

    **Protection des données sensibles:**
    - Les noms propres sont préservés
    - Les dates et entités sont protégées
    - Traitement 100% local (offline)
    """

    INPUT_LABEL = "Texte à corriger"
    INPUT_PLACEHOLDER = "Je sui aller au supermarchet..."
    INPUT_HELP = "Entrez le texte à corriger."

    BTN_CORRECT = "Corriger"
    SECTION_RESULT = "Texte corrigé"
    SECTION_DIFF = "Voir les différences"

    BOOT_TITLE = "Démarrage de DYS-fr…"
    BOOT_SPACY = "Chargement du modèle linguistique…"
    BOOT_LT = "Connexion au correcteur LanguageTool…"
    BOOT_DONE = "DYS-fr est prêt"
    BOOT_LT_WAITING = (
        "Le correcteur LanguageTool démarre. Au premier lancement, cela peut "
        "prendre une trentaine de secondes."
    )

    ERR_NO_TEXT = "Veuillez entrer du texte à corriger."
    ERR_MODEL_NOT_FOUND = "Modèle IA introuvable"

    @staticmethod
    def port_fallback(url: str) -> str:
        return (
            f"Le port habituel était occupé. DYS-fr est accessible à cette "
            f"adresse : {url}"
        )

    @staticmethod
    def install_instructions(model_name: str) -> str:
        return f"""
        **Pour installer le modèle {model_name}:**
        1. Installez le runtime requis (`llama-cpp-python` ou `ollama`).
        2. Placez les modèles locaux dans `%LOCALAPPDATA%\\DYS-fr\\models` ou `resources/models/`.
        3. Redémarrez l'application.
        """

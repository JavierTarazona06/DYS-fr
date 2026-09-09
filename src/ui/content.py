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

    APPEARANCE_TITLE = "Confort de lecture"
    APPEARANCE_FONT_SIZE = "Taille du texte"
    APPEARANCE_FONT_SIZE_HELP = "Agrandit tout le texte de l'application."
    APPEARANCE_LINE_HEIGHT = "Interligne"
    APPEARANCE_LINE_HEIGHT_HELP = (
        "Espace entre les lignes. Un interligne plus large facilite le suivi du texte."
    )
    APPEARANCE_FOCUS = "Mode sans distraction"
    APPEARANCE_FOCUS_HELP = (
        "Masque les menus et le panneau latéral. Un bouton en haut de la page permet "
        "d'en sortir."
    )
    APPEARANCE_FOCUS_EXIT = "Quitter le mode sans distraction"
    APPEARANCE_RESET = "Réinitialiser"

    BOOT_TITLE = "Démarrage de DYS-fr…"
    BOOT_SPACY = "Chargement du modèle linguistique…"
    BOOT_LT = "Connexion au correcteur LanguageTool…"
    BOOT_DONE = "DYS-fr est prêt"
    BOOT_LT_WAITING = (
        "Le correcteur LanguageTool démarre. Au premier lancement, cela peut "
        "prendre une trentaine de secondes."
    )

    MODEL_PANEL_TITLE = "Modèle IA local"
    MODEL_NOT_INSTALLED = "Le modèle IA n'est pas encore téléchargé."
    NO_AI_RUNTIME = "Cette installation n'inclut pas le moteur IA."
    BTN_DOWNLOAD_MODEL = "Télécharger"
    BTN_CANCEL_DOWNLOAD = "Annuler"
    DL_VERIFYING = "Vérification de l'intégrité…"
    DL_DONE = "Modèle installé. Le mode IA est maintenant disponible."
    DL_CANCELLED = "Téléchargement interrompu. Il reprendra où il s'est arrêté."

    ERR_NO_TEXT = "Veuillez entrer du texte à corriger."
    ERR_MODEL_NOT_FOUND = "Modèle IA introuvable"

    @staticmethod
    def download_size(size_bytes: int) -> str:
        return f"{size_bytes / (1024 ** 3):.1f} Go"

    @staticmethod
    def download_progress(done_bytes: int, total_bytes: int) -> str:
        done = done_bytes / (1024 ** 3)
        total = total_bytes / (1024 ** 3)
        return f"Téléchargement : {done:.2f} / {total:.2f} Go"

    @staticmethod
    def ram_warning(required_gb: int, available_gb: int) -> str:
        return (
            f"Ce modèle demande environ {required_gb} Go de mémoire vive ; "
            f"cet ordinateur en a {available_gb} Go. Le mode IA risque d'être très lent."
        )

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

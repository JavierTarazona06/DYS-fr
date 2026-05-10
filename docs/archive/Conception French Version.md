# DYSLangageApp
**French Version**

# Objectif (MVP)

Application locale (Streamlit) qui **reçoit du texte en français** et renvoie une version **corrigée/clarifiée** sans **ajout d’informations nouvelles**. Elle **empêche la triche** : une requête incomplète (« l’année de l’indépendance des États-Unis est le .. de .. ») reste volontairement inachevée. Tout doit fonctionner **hors‑ligne**.

---

# Pile recommandée (réutilisation maximale)

- **Correction grammaticale/style** : **LanguageTool** serveur local (JAR) + wrapper **language-tool-python** (client).
- **LLM local (GGUF)** : **Mistral‑7B‑Instruct v0.3** quantifié (Q4) et **Gemma 3 4B**; sélection de modèle et bascule automatique vers Gemma si Mistral échoue. Service via **llama.cpp** (serveur HTTP) ou **llama‑cpp‑python** (CPU, offload GPU quand dispo).
- **NER et analyse** (garde‑fous) : **spaCy `fr_core_news_md`**.
- **UI** : **Streamlit** (rapide + stable) avec sélecteur « **Léger (règles)** / **Intelligent (hybride)** », barre de progression de téléchargement du modèle, cache et profils **qualité/latence**.
- Fac. **Diff visuel** : **difflib** (standard Python) ou **google-diff-match-patch** (plus précis) configuré pour souligner les ajouts et barrer les suppressions.
- **Gestion des ressources** : détection matériel (RAM/VRAM), limites mémoire, et **offload GPU** quand présent. Les tableaux **GGUF** servent de guide RAM/VRAM.
- **Packaging** : **PyInstaller** (exe) + **Inno Setup** (installateur .exe).
- **Java embarqué** : **JRE** inclus dans l’installateur pour ne rien demander à l’utilisateur.

---

# Structure du projet

```
dys-fr/
  app.py                       # UI Streamlit
  runner.py                    # Lance LT, le serveur LLM et l’app
  config.yaml                  # mode: "regles"|"hybride", model: "mistral-7b-q4"|"gemma3-4b"
  requirements.txt
  src/
    improvers/
      base.py                  # interface TextImprover
      lt_improver.py           # utilise LanguageTool
      llm_improver.py          # LLM local (Mistral/Gemma) + contraintes
    normalize/fr_normalize.py  # nettoyage et segmentation FR
    guardrails/
      entities.py              # spaCy NER + masquage/réinjection
      numbers_dates.py         # regex nombres/dates
      novelty.py               # ratio de tokens nouveaux
      policy.py                # orchestre les vérifications
    utils/
      diff.py                  # helpers pour diffs
      hw.py                    # détection matériel, limites mémoire, GPU
  resources/
    languagetool/languagetool-server.jar
    jre/                       # JRE embarqué
    models/                    # cache de modèles GGUF (Mistral‑7B Q4, Gemma3‑4B)
    bin/llama.cpp/             # binaire serveur (ou wheels llama‑cpp‑python)
    spacy/fr_core_news_md/...
  packaging/
    windows/build.spec         # PyInstaller
    windows/setup.iss          # Inno Setup
  tests/{unit,e2e,adversarial}
  README.md

```

> Route B (hybride) intégrée : `llm_improver.py` implémente la même interface `TextImprover`. Le mode se règle dans `config.yaml` sans toucher à l’UI ni aux garde‑fous.
> 

---

# Pipeline (réutilisation maximale)

1. **Mode “Léger (règles uniquement)”**
    - Normalisation FR : nettoyage des espaces, apostrophes (`l'`, `j'`), tirets, guillemets; segmentation `spaCy`.
    - LanguageTool local : n’applique que les suggestions « sûres » (voir filtres).
    - Garde‑fous : `NER(out) ⊆ NER(in)`, `Digits/Dates(out) ⊆ Digits/Dates(in)`, bloquer PROPN nouveaux, ratio de tokens nouveaux ≤ 10–15 %. Échecs → renvoyer l’entrée normalisée.
    - Post‑traitement FR minimal : espaces avant `; : ? !`, guillemets français optionnels, majuscules.

2. **Mode “Intelligent (hybride)”**
    1) **Pré‑passe (spaCy)** : tokenisation + NER → remplacer les entités par marqueurs.
       Réf. : [huggingface (spaCy fr_core_news_md)](https://huggingface.co/spacy/fr_core_news_md)
    2) **Contrôle rapide (LT)** : corrige erreurs grossières et génère des « pistes » pour le prompt.
       Réf. : [LanguageTool dev](https://dev.languagetool.org/development-overview.html)
    3) **Réécriture (LLM)** : **Mistral‑7B Q4** (ou **Gemma3‑4B** si matériel juste) avec instructions « ne modifie pas les marqueurs/format ».
    4) **Post‑validation (LT)** : si les erreurs **augmentent vs. avant**, **dégrader** vers la sortie LT.
       Réf. : [papier LT](https://www.danielnaber.de/languagetool/download/style_and_grammar_checker.pdf)
    5) **Réinjection d’entités** puis rendu avec **explications** (messages de règles/guide de style).

    - **Sélection/Fallback** : par défaut **Mistral‑7B Q4** si RAM/VRAM suffisantes, sinon **Gemma3‑4B**. En cas d’échec/OOM/health KO du serveur LLM → **bascule automatique** vers Gemma3‑4B.

**Diff** : montre les changements avec `difflib` (ou `diff-match-patch`) en soulignant le texte ajouté et en barrant le texte supprimé.

---

# Filtres “ne pas ajouter d’info”

- **LanguageTool** fournit une liste de *matches* avec *replacements*.
    
    Appliquer **seulement** les remplacements qui :
    
    - N’introduisent pas de **nouveaux nombres/dates**.
    - Ne créent pas de **nouvelles entités** ni de **PROPN**.
    - N’augmentent pas de plus de **N tokens** (ex. N=1) une phrase donnée.
    - Sont dans une **liste blanche** courte (articles, prépositions, contractions, signes).
    - Empêchent la **triche** : si le texte réclame une information manquante (ex. « l’année de l’indépendance des États-Unis est le .. de .. »), la sortie n’invente pas de réponse.

Pour la réécriture LLM, le prompt impose explicitement « ne **modifie pas** les marqueurs/format et **n’ajoute aucune information** ». Un **garde‑fou de dégradation** s’applique : si le score d’erreurs LT post‑LLM > pré‑LLM, on **revient** à la sortie LT.

Ceci est implémenté comme une **fonction de filtrage** recevant les suggestions de LT et décidant lesquelles appliquer. Pas de réécriture des règles : **on réutilise LT**, on **filtre seulement**.

---

# Streamlit (UI minimale et claire)

- Zone de texte large (entrée).
- Bouton **“Corriger”**.
- **Sélecteur de mode** : **“Léger (règles)”** vs **“Intelligent (hybride)”**.
- **Sélecteur de modèle LLM** (si « Intelligent ») : **Gemma3‑4B (~<4 Go RAM)** vs **Mistral‑7B Q4 (meilleure qualité)**.
- **Barre de progression** pour téléchargement/chargement du modèle (cache local), et **profils** de **qualité/latence** (Rapide / Équilibré / Max Qualité).
- Onglets : **“Diff”** (ajouts soulignés, suppressions barrées) et **“Texte final”**.
- Contrôles : taille de police, interligne, contraste élevé (option de thème).
- Étiquette “hors‑ligne / aucune donnée envoyée”.

---

# Runner 1‑clic

- Lance **LanguageTool** avec le **JRE embarqué** :
    
    ```
    resources\\jre\\bin\\java -jar resources\\languagetool\\languagetool-server.jar -l fr -p 8081
    
    ```
    
- Lance (si mode « Intelligent ») un **serveur LLM local** (llama.cpp ou llama‑cpp‑python), avec **offload GPU** si disponible et **limites mémoire** adaptées.
    
    Exemple (llama.cpp, Windows) :
    
    ```
    resources\\bin\\llama.cpp\\server.exe --model resources\\models\\mistral-7b-instruct-q4_k_m.gguf --ctx-size 4096 --port 8082 --n-gpu-layers auto
    ```
    
- Détecte **RAM/VRAM** et choisit le **modèle par défaut** (Mistral‑7B Q4 si OK, sinon Gemma3‑4B). En cas d’erreur/OOM/health KO → **fallback** Gemma3‑4B.
- Attend `http://127.0.0.1:8081/v2/health` (LT) et le health du serveur LLM quand activé.
- Lance **Streamlit** (`streamlit run app.py --server.port 8501`).
- Ouvre le navigateur sur `http://localhost:8501`.
- À la fermeture, tue tous les processus (LT + LLM + Streamlit).

*(Tout cela avec `subprocess` et quelques vérifications simples.)*

---

# Packaging Windows (sans réinventer)

1. **PyInstaller**
    - Spécifie `add-data` pour **resources/** (JRE, LT, spaCy, serveur LLM et/ou wheels `llama-cpp-python`, dossiers `models/` si embarqués).
    - Génère `runner.exe` (mode *windowed* pour ne pas montrer la console).
2. **Inno Setup**
    - Copie dans `C:\\Program Files\\DYS-FR\\`.
    - Crée des raccourcis (Bureau et Menu Démarrer) qui exécutent **runner.exe**.
    - Option “Lancer DYS-FR” à la fin.
    - (Optionnel) Vérification de l’espace disque et version minimale de Windows.

> Résultat : un installateur .exe que l’utilisateur télécharge, suivant‑suivant, terminé, et l’app s’ouvre dans le navigateur. Les **modèles** peuvent être **embarqués** (taille plus grande) ou **téléchargés au premier lancement** dans un **cache local**.
> 

---

# QA (rapide et pratique)

- **Unitaires** : normalisation, parser des suggestions LT, filtres des garde‑fous.
- **E2E** : 20–30 phrases FR typiques (erreurs DYS courantes).
- **Adversariales** :
    - Entrée sans nombres/dates/entités → sortie identique.
    - Noms propres présents → jamais inventer ni modifier.
    - Phrases courtes → ne pas allonger avec des connecteurs inventés.
    - Requêtes incomplètes utilisées pour **tricher** (« l’année de l’indépendance des États-Unis est le .. de .. ») → la sortie reste incomplète.
- **Hybride** : vérifie que les **marqueurs d’entités** ne sont jamais altérés par le LLM; si le score LT **augmente** après LLM, on **dégrade** vers LT; **fallback** vers Gemma3‑4B testé (simule OOM).
- **Performance** : < 1 s pour 1–2 phrases (mode Léger) et budget mesuré pour **chargement modèle** + **latence LLM** (barre de progression).

---

# Plan de travail (gain de temps)

**Phase 0 – Setup (3–5 h)**

- Repo, venv, `requirements.txt`, structure dossiers, `config.yaml`.

**Phase 1 – Ressources hors‑ligne (5–7 h)**

- Copier JAR de LT, **JRE** embarqué, spaCy FR.
- Scripts de vérification des chemins.

**Phase 2 – Noyau NLP (12–16 h)**

- Connecteur LanguageTool (client) + **filtre** de suggestions.
- **Composant LLM local** (Mistral/Gemma) + prompts contraints (« ne pas modifier marqueurs/format ») + **fallback**.
- Normalisation + post‑traitement FR.

**Phase 3 – Garde‑fous (8–12 h)**

- `spaCy` NER/PROPN.
- Regex nombres/dates.
- Ratio de tokens nouveaux (lemmes).
- Fallback sûr.

**Phase 4 – UI Streamlit (6–8 h)**

- Écran unique : entrée → bouton → Diff / Résultat.
- Contrôles d’accessibilité de base.
- Diff avec `difflib` / `diff-match-patch` configuré pour souligner les ajouts et barrer les suppressions.

**Phase 5 – Runner + Packaging (10–14 h)**

- `runner.py` (LT + **serveur LLM** + ouverture navigateur + fermeture) avec **détection matériel** et **offload GPU** quand présent.
- PyInstaller (exe) + Inno Setup (installateur) avec ressources **JRE/LT/spaCy/LLM** et **cache de modèles**.
- Test d’installation sur Windows “propre”.

**Phase 6 – QA & Docs (6–8 h)**

- Tests e2e/adversariaux.
- README/Guide d’utilisation (3–5 captures).
- Notes de confidentialité (hors‑ligne).

**Marge (10–15 %) (6–9 h)**

**Total estimé (sans TTS, Windows uniquement) :** **50–71 heures** (typique ~60–65 h).

> Pour réduire encore : omettre Hunspell (laisser LT + garde‑fous) et utiliser seulement difflib → ~45–55 h.
> 

---

# Livrables du MVP

- **Installateur Windows (.exe)** avec tout embarqué (LT + JRE + spaCy + **serveur LLM** + **modèles** ou **téléchargement au premier lancement**).
- Application **hors‑ligne** : coller du texte → “Corriger” → voir **Diff** et **Texte final**.
- **Zéro dépendance externe** (ni Java ni Internet), hors téléchargement initial éventuel des modèles.
- Code organisé pour **mode Léger** et **mode Intelligent (hybride)**, avec **sélection de modèle** et **fallback**.


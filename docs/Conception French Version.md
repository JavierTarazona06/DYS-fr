# French Version

# Objectif (MVP)

Application locale (Streamlit) qui **reçoit du texte en français** et renvoie une version **corrigée/clarifiée** sans **ajout d’informations nouvelles**. Tout doit fonctionner **hors‑ligne**.

---

# Pile recommandée (réutilisation maximale)

- **Correction grammaticale/style** : **LanguageTool** serveur local (JAR) + wrapper **language-tool-python** (client).
- **Orthographe** : **Hunspell fr_FR** (via `hunspell` ou, plus simple, `pyspellchecker` FR).
- **NER et analyse** (garde‑fous) : **spaCy `fr_core_news_md`**.
- **UI** : **Streamlit** (rapide + stable).
- **Diff visuel** : **difflib** (standard Python) ou **google-diff-match-patch** (plus précis).
- **Packaging** : **PyInstaller** (exe) + **Inno Setup** (installateur .exe).
- **Java embarqué** : **JRE** inclus dans l’installateur pour ne rien demander à l’utilisateur.

---

# Structure du projet

```
dys-fr/
  app.py                       # UI Streamlit
  runner.py                    # Lance LT et l’app, ouvre le navigateur
  config.yaml                  # improver: "lt"
  requirements.txt
  src/
    improvers/
      base.py                  # interface TextImprover
      lt_improver.py           # utilise LanguageTool + Hunspell
    normalize/fr_normalize.py  # nettoyage et segmentation FR
    guardrails/
      entities.py              # spaCy NER
      numbers_dates.py         # regex nombres/dates
      novelty.py               # ratio de tokens nouveaux
      policy.py                # orchestre les vérifications
    utils/diff.py              # helpers pour diffs
  resources/
    languagetool/languagetool-server.jar
    jre/                       # JRE embarqué
    hunspell/fr_FR.dic
    hunspell/fr_FR.aff
    spacy/fr_core_news_md/...
  packaging/
    windows/build.spec         # PyInstaller
    windows/setup.iss          # Inno Setup
  tests/{unit,e2e,adversarial}
  README.md

```

> Préparé pour la Route B : plus tard, on ajoute ml_improver.py qui implémente la même interface TextImprover et on change seulement config.yaml.
> 

---

# Pipeline (réutilisation maximale)

1. **Normalisation FR** (réutilisation) :
    - Nettoyage des espaces, apostrophes (`l'`, `j'`), tirets, guillemets.
    - Segmentation des phrases : `spacy` ou `nltk` (utilise `spacy` déjà chargé).
2. **LanguageTool local** :
    - Appelle le serveur LT et **applique uniquement les suggestions “sûres”** (voir filtrage ci‑dessous).
3. **Hunspell** :
    - Mots hors dictionnaire → suggestions de remplacement 1:1 (sans ajouter de mots complexes).
4. **Garde‑fous** (post‑filtrage) :
    - `NER(out) ⊆ NER(in)` avec `spaCy`.
    - `Digits/Dates(out) ⊆ Digits/Dates(in)` avec regex.
    - **Bloquer les PROPN** nouveaux (POS spaCy).
    - **Ratio de tokens nouveaux** ≤ 10–15 % (comptage des lemmes de contenu).
    - Si une édition enfreint les règles → elle est rejetée ; si la sortie échoue totalement → renvoyer **l’entrée normalisée**.
5. **Post‑traitement FR** (minimal) :
    - Espaces avant `; : ? !`, guillemets français optionnels, majuscules.

**Diff** : montre les changements avec `difflib` (ou `diff-match-patch`).

---

# Filtres “ne pas ajouter d’info”

- **LanguageTool** fournit une liste de *matches* avec *replacements*.
    
    Appliquer **seulement** les remplacements qui :
    
    - N’introduisent pas de **nouveaux nombres/dates**.
    - Ne créent pas de **nouvelles entités** ni de **PROPN**.
    - N’augmentent pas de plus de **N tokens** (ex. N=1) une phrase donnée.
    - Sont dans une **liste blanche** courte (articles, prépositions, contractions, signes).

Ceci est implémenté comme une **fonction de filtrage** recevant les suggestions de LT et décidant lesquelles appliquer. Pas de réécriture des règles : **on réutilise LT**, on **filtre seulement**.

---

# Streamlit (UI minimale et claire)

- Zone de texte large (entrée).
- Bouton **“Améliorer”**.
- Onglets : **“Diff”** (rouge/vert) et **“Texte final”**.
- Contrôles : taille de police, interligne, contraste élevé (option de thème).
- Étiquette “hors‑ligne / aucune donnée envoyée”.

---

# Runner 1‑clic

- Lance **LanguageTool** avec le **JRE embarqué** :
    
    ```
    resources\\jre\\bin\\java -jar resources\\languagetool\\languagetool-server.jar -l fr -p 8081
    
    ```
    
- Attend `http://127.0.0.1:8081/v2/health`.
- Lance **Streamlit** (`streamlit run app.py --server.port 8501`).
- Ouvre le navigateur sur `http://localhost:8501`.
- À la fermeture, tue les deux processus (LT + Streamlit).

*(Tout cela avec `subprocess` et quelques vérifications simples.)*

---

# Packaging Windows (sans réinventer)

1. **PyInstaller**
    - Spécifie `add-data` pour **resources/** (JRE, LT, spaCy, Hunspell).
    - Génère `runner.exe` (mode *windowed* pour ne pas montrer la console).
2. **Inno Setup**
    - Copie dans `C:\\Program Files\\DYS-FR\\`.
    - Crée des raccourcis (Bureau et Menu Démarrer) qui exécutent **runner.exe**.
    - Option “Lancer DYS-FR” à la fin.
    - (Optionnel) Vérification de l’espace disque et version minimale de Windows.

> Résultat : un installateur .exe que l’utilisateur télécharge, suivant-suivant, terminé, et l’app s’ouvre dans le navigateur.
> 

---

# QA (rapide et pratique)

- **Unitaires** : normalisation, parser des suggestions LT, filtres des garde‑fous.
- **E2E** : 20–30 phrases FR typiques (erreurs DYS courantes).
- **Adversariales** :
    - Entrée sans nombres/dates/entités → sortie identique.
    - Noms propres présents → jamais inventer ni modifier.
    - Phrases courtes → ne pas allonger avec des connecteurs inventés.
- **Performance** : < 1 s pour 1–2 phrases sur un portable standard.

---

# Plan de travail (gain de temps)

**Phase 0 – Setup (3–5 h)**

- Repo, venv, `requirements.txt`, structure dossiers, `config.yaml`.

**Phase 1 – Ressources hors‑ligne (5–7 h)**

- Copier JAR de LT, **JRE** embarqué, dictionnaires Hunspell FR, spaCy FR.
- Scripts de vérification des chemins.

**Phase 2 – Noyau NLP (12–16 h)**

- Connecteur LanguageTool (client) + **filtre** de suggestions.
- Étape Hunspell (fallback orthographique).
- Normalisation + post‑traitement FR.

**Phase 3 – Garde‑fous (8–12 h)**

- `spaCy` NER/PROPN.
- Regex nombres/dates.
- Ratio de tokens nouveaux (lemmes).
- Fallback sûr.

**Phase 4 – UI Streamlit (6–8 h)**

- Écran unique : entrée → bouton → Diff / Résultat.
- Contrôles d’accessibilité de base.
- Diff avec `difflib` / `diff-match-patch`.

**Phase 5 – Runner + Packaging (10–14 h)**

- `runner.py` (gestion des processus + ouverture navigateur + fermeture).
- PyInstaller (exe) + Inno Setup (installateur).
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

- **Installateur Windows (.exe)** avec tout embarqué (LT + JRE + spaCy + Hunspell).
- Application **hors‑ligne** : coller du texte → “Améliorer” → voir **Diff** et **Texte final**.
- **Zéro dépendance externe** (ni Java ni Internet).
- Code organisé pour **activer la Route B** plus tard sans toucher à l’UI ni aux garde‑fous.


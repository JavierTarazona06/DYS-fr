# Guide d'Exécution des Tests

Ce document explique comment exécuter les tests automatisés du projet DYS-fr.

## Prérequis

Assurez-vous que votre environnement virtuel est activé :

```powershell
# Windows
.\.venv\Scripts\Activate.ps1
```

Assurez-vous également que le serveur LanguageTool est démarré si vous exécutez des tests qui en dépendent (bien que certains tests tentent de le détecter automatiquement).

## Options Utiles

*   `-v` (**verbose**) : Affiche plus de détails sur chaque test exécuté.
*   `-s` (**no capture**) : Affiche les sorties `print()` et les logs dans la console (utile pour le débogage).

---

## 1. Exécuter Tous les Tests

Pour lancer l'ensemble de la suite de tests (LanguageTool, Mistral, spaCy) :

```powershell
pytest tests/ -v -s
```

---

## 2. Exécuter un Fichier de Test Spécifique

Vous pouvez cibler un fichier particulier pour tester un composant spécifique.

### Tests LanguageTool
Vérifie la connectivité au serveur et les corrections de base.
```powershell
pytest tests/test_languagetool.py -v -s
```

### Tests Mistral LLM
Vérifie le chargement du modèle, les corrections intelligentes et la préservation du sens.
```powershell
pytest tests/test_llm_mistral.py -v -s
```

### Tests spaCy
Vérifie la détection d'entités nommées (NER) et le masquage.
```powershell
pytest tests/test_spacy.py -v -s
```

---

## 3. Exécuter une Fonction de Test Spécifique

Pour n'exécuter qu'un seul cas de test, utilisez la syntaxe `::nom_de_la_fonction` après le nom du fichier.

### Exemples pour Mistral

Tester uniquement le chargement du modèle :
```powershell
pytest tests/test_llm_mistral.py::test_mistral_loading -v -s
```

Tester la correction d'un paragraphe dyslexique complet :
```powershell
pytest tests/test_llm_mistral.py::test_mistral_dyslexic_paragraph -v -s
```

### Exemples pour LanguageTool

Tester uniquement la connectivité serveur :
```powershell
pytest tests/test_languagetool.py::test_lt_server_connectivity -v -s
```

### Exemples pour spaCy

Tester uniquement la détection d'entités :
```powershell
pytest tests/test_spacy.py::test_spacy_entity_detection -v -s
```

# Spécifications

## Moteur DYS

[Moteur DYS](Moteur%20DYS%2027a461b2c1a480fab4daca3a57c66e9b.md)

## UI accessible

[UI accessible ](UI%20accessible%2027a461b2c1a48067b383d6a514658e01.md)

## QA

[QA](QA%2027a461b2c1a4803b8fb4d3e917e47557.md)

# Approche DYS

## Impact sur l’effort (par rapport au plan sans TTS, Windows)

- **Ajustements du moteur et filtres DYS** : +3–5 h
- **UI accessible (CSS + contrôles)** : +3–4 h
- **QA DYS (jeu + métriques + adversariaux)** : +4–6 h
    
    **Total extra** : **~10–15 h** pour être réellement orienté DYS.
    

*(Toujours dans la fourchette de la version “complète” prévue ; pas besoin d’outils nouveaux.)*

---

## Résumé

- **Oui**, ta version avec **LT + Hunspell + spaCy + Streamlit + diff + PyInstaller/Inno + JRE** **est parfaitement viable pour les utilisateurs finaux DYS**.
- Qualité DYS assurée : **éditions “DYS‑safe”**, **UI à faible fatigue**, et **QA avec métriques de lisibilité**.
- Tout est fait par **réutilisation d’outils** et règles de **filtrage/garde‑fous**, sans inventer ni ajouter TTS ou modèles nouveaux.
- Prête, si souhaité, à **activer la Route B** ensuite sans toucher à l’UI ni à la sécurité “ne pas ajouter d’info”.
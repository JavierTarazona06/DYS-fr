# QA

## 3) QA centré sur DYS (en plus de la correction)

Préparer un ensemble de 25–40 textes courts **réels ou simulés** avec erreurs DYS (anonymisés).

**Métriques suggérées pour “apte utilisateurs finaux” :**

- **Ajouts illégaux** (entités/dates/nombres) = **0 %**.
- **Erreur orthographique/grammaticale** : réduction **≥80 %** (compte pré/post avec LT).
- **Longueur moyenne de phrase** : si mode “Équilibré”, ne doit pas dépasser **30–35** mots ; en mode “Plus simple”, **≤28**.
- **Lisibilité (FR)** : amélioration d’un indicateur proxy (par ex. **syllabes/phrase** ou **caractères/phrase**).
- **Feedback de 6–8 utilisateurs DYS** :
    - « Est-ce plus clair pour toi ? » (1–5) → **≥4** en moyenne.
    - « Est-ce moins fatigant à lire ? » (1–5) → **≥4**.

**Tests adversariaux (indispensables) :**

- Entrée sans nombres/dates/entités → sortie identique.
- Nom propre présent → reste inchangé.
- Phrases de 4–6 mots → **ne** s’allongent pas avec des connecteurs.
- Texte mixte (FR + sigles/URLs) → ne “corrige” pas l’URL/sigle.
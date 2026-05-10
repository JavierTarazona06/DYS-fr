# Moteur DYS

## 1) Moteur (éditions “DYS-safe”, sans ajout d’info)

On garde LT/Hunspell, mais on **filtre et on priorise** ces transformations :

**Autorisées (n’ajoutent pas de contenu) :**

- **Correction orthographique et accents** : “J ai oublier” → “J’ai oublié”.
- **Ajustement des élisions** et apostrophes : “qu il” → “qu’il”.
- **Ponctuation française** et espaces fines : avant `; : ? !`.
- **Segmentation douce** : diviser une phrase trop longue **en 2** (maximum) si LT le suggère ou si elle dépasse par ex. **30–35 mots**.
- **Réordonnancements minimaux** S–V–O quand LT le propose (sans introduire de nouveaux connecteurs longs).

**Restreintes / bloquées :**

- **Connecteurs nouveaux** (“En effet”, “Par conséquent”, etc.) → bloquer s’ils n’étaient pas présents.
- **Paraphrases étendues** ou expansion de >15 % des tokens.
- **Noms propres (PROPN)** nouveaux ou modifiés.
- **Nombres/dates** nouveaux.
- **Néologismes ou termes peu fréquents** (utiliser un petit lexique de haute fréquence FR comme “whitelist”).

**Heuristiques utiles pour DYS :**

- **Homophones fréquents** (et/est, a/à, ou/où, ce/se, on/ont, son/sont, ces/ses, la/là) → accepter le remplacement si **le rôle grammatical ne change pas** et que cela améliore l’accord.
- **Inversions de lettres** typiques (oi↔io, eu↔ue) → autoriser si Hunspell/LT le valide.
- **Duplications/omissions** (“llll”, accent manquant) → toujours corriger.

**Garde-fous déjà prévus (à activer par défaut) :**

- `NER(out) ⊆ NER(in)`, `Numbers/Dates(out) ⊆ Numbers/Dates(in)`.
- **Blocage des PROPN** nouveaux (POS spaCy).
- **Ratio de tokens nouveaux** (lemmes de contenu) ≤ **10–12 %** (un peu plus strict pour DYS).
- Si échec, renvoyer **l’entrée normalisée** (sûre).

**“Niveau d’intervention” (slider simple) :**

- **Fidèle** : seulement orthographe/accents/ponctuation.
- **Équilibré (par défaut)** : + segmentation douce et réordonnancements minimaux.
- **Plus simple** : active une limite de longueur de phrase (par ex. 25–28 mots), mais **sans ajouter d’exemples ni de connecteurs**.

*(Ceci est un drapeau dans ton filtre ; pas besoin de nouveaux modèles.)*

## Petits extras utiles (sans “réinventer la roue”)

- **Dictionnaire utilisateur** (optionnel) : TXT avec mots “autorisés” (noms de famille, toponymes, jargon scolaire). Chargé depuis `resources/`.
- **Gabarits d’erreurs DYS** (JSON) pour les tests : 10–12 patrons (inversion, duplication, accent omis…).
- **Journal local** (toggle) : montre combien de suggestions LT ont été rejetées par les garde-fous (aide à ajuster les seuils).
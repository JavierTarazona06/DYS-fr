# UI accessible

# UI accessible (Streamlit, sans TTS)

Objectif : révision sans fatigue et avec focalisation.

Polices lisibles : Lexend, Atkinson Hyperlegible ou OpenDyslexic (chargement local via `st.markdown(unsafe_allow_html=True)` et CSS).

Contrôles visibles : taille de police (120–200 %), interligne (1,4–1,8), largeur de colonne (60–80 caractères par ligne).

Mode focus :

- Masquer les panneaux latéraux, afficher une seule colonne.
- Surlignage de la ligne au survol (CSS simple) pour éviter les sauts de ligne.

Diff clair :

- Supprimé = barré rouge ; Remplacement = rouge → vert ; Inséré = vert.
- Boutons : « Voir les changements » / « Texte final ».

Grands boutons : « Améliorer », « Copier le texte », « Réinitialiser ».

Messages courts et littéraux : sans jargon technique, sans animations.

Mode haut contraste : fond #111, texte #EEE, liens et marquages soulignés.

(Tout cela est du CSS + options Streamlit ; n’ajoute pas de complexité fonctionnelle.)
# UI Accesible

1. UI accesible (Streamlit, sin TTS)

Objetivo: revisión sin fatiga y foco.

Tipografías legibles: Lexend, Atkinson Hyperlegible o OpenDyslexic (carga local con st.markdown(unsafe_allow_html=True) y CSS).

Controles visibles: tamaño de fuente (120–200%), interlineado (1.4–1.8), ancho de columna (60–80 caracteres por línea).

Modo foco:

Oculta paneles laterales, muestra una sola columna.

Resaltado de línea al pasar el mouse (CSS simple) para evitar saltos de renglón.

Diff claro:

Eliminado = tachado rojo; Reemplazo = rojo→verde; Insertado = verde.

Botones: “Ver cambios” / “Texto final”.

Botones grandes: “Améliorer”, “Copier le texte”, “Réinitialiser”.

Mensajes cortos y literales: sin jerga técnica, sin animaciones.

Modo alto contraste: fondo #111, texto #EEE, enlaces y marcas con subrayado.

(Todo esto es CSS + opciones de Streamlit; no añade complejidad funcional.)
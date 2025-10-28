# QA

## 3) QA centrado en DYS (además de corrección)

Prepara un set de 25–40 textos cortos **reales o simulados** con errores DYS (anonimizados).

**Métricas sugeridas para “apto usuarios finales”:**

- **Adiciones ilegales** (entidades/fechas/números) = **0%**.
- **Error ortográfico/gramatical**: reducción **≥80%** (cuenta pre/post con LT).
- **Longitud media de frase**: si activas “Equilibrado”, que **no exceda 30–35** palabras; en “Más simple”, **≤28**.
- **Legibilidad (FR)**: mejora de un indicador proxy (p. ej., **syllabes/phrase** o **caractères/phrase**).
- **Feedback de 6–8 usuarios DYS**:
    - “¿Te resulta más claro?” (1–5) → **≥4** promedio.
    - “¿Te cansa menos leerlo?” (1–5) → **≥4**.

**Pruebas adversariales (imprescindibles):**

- Entrada sin números/fechas/entidades → salida igual.
- Nombre propio presente → se mantiene idéntico.
- Frases de 4–6 palabras → **no** se expanden con conectores.
- Texto mixto (FR + siglas/URLs) → no “corrige” la URL/sigla.
# Motor DYS

## 1) Motor (ediciones “DYS-safe”, sin añadir info)

Mantienes LT/Hunspell, pero **filtras y priorizas** estas transformaciones:

**Permitidas (no añaden contenido):**

- **Corrección ortográfica y acentos**: “J ai oublier” → “J’ai oublié”.
- **Ajuste de elisiones** y apóstrofos: “qu il” → “qu’il”.
- **Puntuación francesa** y espacios finos: antes de `; : ? !`.
- **Segmentación suave**: dividir una frase demasiado larga **en 2** (máximo) si LT lo sugiere o si supera p. ej. **30–35 palabras**.
- **Reordenamientos mínimos** S–V–O cuando LT lo proponga (sin introducir conectores nuevos largos).

**Restringidas / bloqueadas:**

- **Conectores nuevos** (“En effet”, “Par conséquent”, etc.) → bloquear si no estaban.
- **Paráfrasis extensas** o expansión de >15% tokens.
- **Nombres propios (PROPN)** nuevos o modificados.
- **Números/fechas** nuevas.
- **Neologismos o términos poco frecuentes** (usa un pequeño lexicón de alta frecuencia FR para “whitelist”).

**Heurísticas útiles para DYS:**

- **Homófonos frecuentes** (et/est, a/à, ou/où, ce/se, on/ont, son/sont, ces/ses, la/là) → acepta reemplazo si **no cambia el rol gramatical** y mejora acuerdo.
- **Inversiones de letras** típicas (oi↔io, eu↔ue) → permitir si Hunspell/LT lo respalda.
- **Duplicaciones/omisiones** (“llll”, falta de acento) → corregir siempre.

**Guardrails ya previstos (actívalos por defecto):**

- `NER(out) ⊆ NER(in)`, `Numbers/Dates(out) ⊆ Numbers/Dates(in)`.
- **Bloqueo de PROPN** nuevos (spaCy POS).
- **Ratio de tokens nuevos** (lemmas de contenido) ≤ **10–12%** (ligeramente más estricto para DYS).
- Si falla, devolver **entrada normalizada** (segura).

**“Nivel de intervención” (slider simple):**

- **Fiel**: sólo ortografía/acentos/puntuación.
- **Equilibrado (por defecto)**: + segmentación suave y reordenamientos mínimos.
- **Más simple**: activa tope de longitud de frase (p. ej., 25–28 palabras), pero **sin añadir ejemplos ni conectores**.

*(Esto es una bandera en tu filtro; no requiere modelos nuevos.)*

## Pequeños extras que ayudan (sin “reinventar la rueda”)

- **Diccionario del usuario** (opcional): TXT con palabras “permitidas” (apellidos, topónimos, jerga escolar). Se carga desde `resources/`.
- **Plantillas de errores DYS** (JSON) para tests: 10–12 patrones (inversión, duplicación, acento omitido…).
- **Registro local** (toggle): muestra cuántas sugerencias LT se descartaron por guardrails (te ayuda a ajustar umbrales).
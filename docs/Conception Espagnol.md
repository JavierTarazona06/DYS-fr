# Conception

[French Version](French%20Version%2027a461b2c1a480e89025f80bf1730671.md)

# Objetivo (MVP)

App local (Streamlit) que **recibe texto en francés** y devuelve una versión **corregida/clarificada** sin **añadir información nueva**. Todo **offline**.

---

# Pila recomendada (máximo reuso)

- **Corrección gramatical/estilo**: **LanguageTool** servidor local (JAR) + wrapper **language-tool-python** (cliente).
- **Ortografía**: **Hunspell fr_FR** (vía `hunspell` o, si prefieres simplicidad, `pyspellchecker` FR).
- **NER y análisis** (guardrails): **spaCy `fr_core_news_md`**.
- **UI**: **Streamlit** (rápido + estable).
- **Diff visual**: **difflib** (estándar Python) o **google-diff-match-patch** (más fino).
- **Empaquetado**: **PyInstaller** (exe) + **Inno Setup** (instalador .exe).
- **Java embebido**: **JRE** dentro del instalador para no pedirle nada al usuario.

---

# Estructura del proyecto

```
dys-fr/
  app.py                       # UI Streamlit
  runner.py                    # Arranca LT y la app, abre navegador
  config.yaml                  # improver: "lt"
  requirements.txt
  src/
    improvers/
      base.py                  # interface TextImprover
      lt_improver.py           # usa LanguageTool + Hunspell
    normalize/fr_normalize.py  # limpieza y segmentación FR
    guardrails/
      entities.py              # spaCy NER
      numbers_dates.py         # regex números/fechas
      novelty.py               # ratio de tokens nuevos
      policy.py                # orquesta checks
    utils/diff.py              # helpers para diffs
  resources/
    languagetool/languagetool-server.jar
    jre/                       # JRE embebido
    hunspell/fr_FR.dic
    hunspell/fr_FR.aff
    spacy/fr_core_news_md/...
  packaging/
    windows/build.spec         # PyInstaller
    windows/setup.iss          # Inno Setup
  tests/{unit,e2e,adversarial}
  README.md

```

> Preparado para Ruta B: en el futuro agregas ml_improver.py que implemente la misma interfaz TextImprover y sólo cambias config.yaml.
> 

---

# Pipeline (reutilizando al máximo)

1. **Normalización FR** (reuso):
    - Limpia espacios, apóstrofos (`l'`, `j'`), guiones, comillas.
    - Segmentación de oraciones: `spacy` o `nltk` (usa `spacy` ya cargado).
2. **LanguageTool local**:
    - Llama al servidor LT y **aplica sólo sugerencias “seguras”** (ver filtrado abajo).
3. **Hunspell**:
    - Palabras fuera de diccionario → sugerencias de reemplazo 1:1 (sin añadir nuevas palabras complejas).
4. **Guardrails** (post-filtro):
    - `NER(out) ⊆ NER(in)` con `spaCy`.
    - `Digits/Dates(out) ⊆ Digits/Dates(in)` con regex.
    - **Bloquear PROPN** nuevos (spaCy POS).
    - **Ratio de tokens nuevos** ≤ 10–15% (cuenta de lemmas de contenido).
    - Si una edición rompe reglas → se descarta esa edición; si la salida total falla → devolver **entrada normalizada**.
5. **Postproceso FR** (mínimo):
    - Espacios antes de `; : ? !`, comillas francesas opcional, mayúsculas.

**Diff**: muestra cambios con `difflib` (o `diff-match-patch`).

---

# Filtros “no añadir info” (con lo ya existente)

- **LanguageTool** trae una lista de *matches* con *replacements*.
    
    Aplica **sólo** reemplazos que:
    
    - No introduzcan **nuevos números/fechas**.
    - No creen **nuevas entidades** ni **PROPN**.
    - No aumenten en más de **N tokens** (p. ej., N=1) una oración dada.
    - Estén en una **whitelist** corta (artículos, preposiciones, contracciones, signos).

Esto se implementa como una **función de filtro** que recibe las sugerencias de LT y decide cuáles aplicar. No reescribes reglas: **reusas LT**, sólo **filtras**.

---

# Streamlit (UI mínima y clara)

- Área de texto grande (entrada).
- Botón **“Améliorer”**.
- Pestañas: **“Diff”** (rojo/verde) y **“Texte final”**.
- Controles: tamaño de fuente, interlineado, alto contraste (opción de tema).
- Etiqueta “offline / no se envían datos”.

---

# Runner para 1-clic

- Lanza **LanguageTool** con el **JRE embebido**:
    
    ```
    resources\jre\bin\java -jar resources\languagetool\languagetool-server.jar -l fr -p 8081
    
    ```
    
- Espera a `http://127.0.0.1:8081/v2/health`.
- Lanza **Streamlit** (`streamlit run app.py --server.port 8501`).
- Abre el navegador en `http://localhost:8501`.
- Al cerrar, mata ambos procesos (LT + Streamlit).

*(Todo esto con `subprocess` y comprobaciones simples.)*

---

# Empaquetado Windows (sin reinventar)

1. **PyInstaller**
    - Especifica `-add-data` para **resources/** (JRE, LT, spaCy, Hunspell).
    - Genera `runner.exe` (modo *windowed* para no mostrar consola).
2. **Inno Setup**
    - Copia a `C:\Program Files\DYS-FR\`.
    - Crea accesos directos (Escritorio y Menú Inicio) que ejecuten **runner.exe**.
    - Opción “Iniciar DYS-FR” al finalizar.
    - (Opcional) Comprobación de espacio en disco y versión mínima de Windows.

> Resultado: un instalador .exe que el usuario descarga, siguiente-siguiente, termina, y se abre la app en el navegador.
> 

---

# QA (rápido y práctico)

- **Unitarias**: normalización, parser de sugerencias LT, filtros de guardrails.
- **E2E**: 20–30 frases FR típicas (errores DYS comunes).
- **Adversariales**:
    - Entrada sin números/fechas/entidades → salida igual.
    - Nombres propios presentes → nunca inventar ni cambiar.
    - Frases cortas → no expandir con conectores inventados.
- **Rendimiento**: < 1 s por 1–2 frases en portátil estándar.

---

# Plan de trabajo (ahorro de tiempo)

**Fase 0 – Setup (3–5 h)**

- Repo, venv, `requirements.txt`, estructura carpetas, `config.yaml`.

**Fase 1 – Recursos offline (5–7 h)**

- Copiar JAR de LT, **JRE** embebido, diccionarios Hunspell FR, spaCy FR.
- Scripts de verificación de rutas.

**Fase 2 – Núcleo NLP (12–16 h)**

- Conector LanguageTool (cliente) + **filtro** de sugerencias.
- Paso Hunspell (fallback ortográfico).
- Normalización + postproceso FR.

**Fase 3 – Guardrails (8–12 h)**

- `spaCy` NER/PROPN.
- Regex números/fechas.
- Ratio de tokens nuevos (lemmas).
- Fallback seguro.

**Fase 4 – UI Streamlit (6–8 h)**

- Pantalla única: entrada → botón → Diff / Resultado.
- Controles de accesibilidad básicos.
- Diff con `difflib` / `diff-match-patch`.

**Fase 5 – Runner + Packaging (10–14 h)**

- `runner.py` (gestión de procesos + apertura navegador + cierre).
- PyInstaller (exe) + Inno Setup (instalador).
- Prueba de instalación en Windows “limpio”.

**Fase 6 – QA & Docs (6–8 h)**

- Tests e2e/adversariales.
- README/Guía de uso (3–5 capturas).
- Notas de privacidad (offline).

**Reserva (10–15%) (6–9 h)**

**Total estimado (sin TTS, Windows only):** **50–71 horas** (típico ~60–65 h).

> Si necesitas aún más recorte: omite Hunspell (deja sólo LT + guardrails) y usa difflib simple → ~45–55 h.
> 

---

# Entregables del MVP

- **Instalador Windows (.exe)** con todo embebido (LT + JRE + spaCy + Hunspell).
- App **offline**: pegar texto → “Améliorer” → ver **Diff** y **Texto final**.
- **Cero dependencias externas** (ni Java ni Internet).
- Código organizado para **activar Ruta B** en el futuro sin tocar la UI ni los guardrails.

# Especificaciones

## Motor DYS

[Motor DYS](Motor%20DYS%2027a461b2c1a480e5b7aad9e46466b96f.md)

## UI accesible

[UI Accesible](UI%20Accesible%2027a461b2c1a4804aa8e0d2831b541137.md)

## QA

[QA](QA%2027a461b2c1a4802ab082f2ae1decefd3.md)

# Enfoque DYS

## Impacto en esfuerzo (sobre tu plan sin TTS, Windows)

- **Ajustes de motor y filtros DYS**: +3–5 h
- **UI accesible (CSS + controles)**: +3–4 h
- **QA DYS (set + métricas + adversariales)**: +4–6 h
    
    **Total extra**: **~10–15 h** para quedar realmente orientado a DYS.
    

*(Sigues dentro del rango de tu versión “completa” prevista; no requiere herramientas nuevas.)*

---

## Resumen

- **Sí**, tu versión con **LT + Hunspell + spaCy + Streamlit + diff + PyInstaller/Inno + JRE** **es perfectamente viable para usuarios finales DYS**.
- Asegura calidad DYS: **ediciones “DYS-safe”**, **UI de baja fatiga**, y **QA con métricas de legibilidad**.
- Todo se implementa con **reuso de herramientas** y reglas de **filtro/guardrails**, sin inventar nada ni añadir TTS ni modelos nuevos.
- Queda lista para, si gusta, **activar Ruta B** luego sin tocar la UI ni la seguridad de “no añadir info”.
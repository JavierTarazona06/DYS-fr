# Propuestas de rendimiento: inferencia local (Gemma y Mistral) en PC sin GPU dedicada

Rol asumido: ingeniero de rendimiento especializado en inferencia local de LLMs (Gemma/Mistral) en hardware de consumo, con foco en un despliegue realista (PC de usuario promedio o computadores de un centro educativo en Francia).

---

## Hechos comprobados (solo a partir de los adjuntos del proyecto)

### Arquitectura y flujo

- El proyecto es una app **offline** en **Streamlit** (`app.py`) que ofrece:
  - **Modo “Léger / Light”**: correcciones con **LanguageTool** + guardrails.
  - **Modo “Hybride / Hybrid”**: **LanguageTool (pre)** → **LLM** → **LanguageTool (post-validación)**; si el post empeora (más errores), **revierte** la salida al texto de entrada enmascarado. (`src/improvers/llm_improver.py`, `src/improvers/ollama_improver.py`)
- En modo híbrido, el UI permite elegir modelo:
  - **Mistral 7B (Local GGUF)** embebido.
  - **Gemma 3 (Ollama)** vía servidor local de Ollama.
  - En el sidebar, el radio tiene `index=1`, por lo que **Gemma (Ollama) queda seleccionado por defecto** al entrar al modo híbrido. (`src/ui/layout.py`)
- **LanguageTool** se ejecuta como servidor Java local y el `runner.py` lo auto-inicia antes de lanzar Streamlit. (`runner.py`, `scripts/start_lt_server_automatic.py`, `src/improvers/lt_server.py`)

### Modelos/backends y configuración relevante

- **Mistral**:
  - Se usa **`llama-cpp-python`** (`llama_cpp.Llama`) con un modelo **GGUF** configurado en `config.yaml` como `resources/models/Mistral-7B-Instruct-v0.3-Q4_K_M.gguf`.
  - Carga del modelo en `LLMImprover`:
    - `n_gpu_layers=0` (CPU-only)
    - `n_threads = os.cpu_count()` (por defecto)
    - `n_ctx` (por defecto 4096, también en `config.yaml`)
    - `use_mlock=True`, `use_mmap=True`, `verbose=False`. (`src/improvers/llm_improver.py`)
  - Generación:
    - `max_tokens` efectivo: `min(config.max_tokens, max(50, 4 * palabras_del_texto))`
    - `temperature=0.1`, `top_p=0.85`, `repeat_penalty=1.1`
    - `stop=["</s>", "[INST]"]` (sin streaming en la UI). (`src/improvers/llm_improver.py`)
- **Gemma**:
  - Se usa **Ollama** vía `ollama.chat(...)` con el `model_name` de `config.yaml` (por defecto `gemma3:4b`). (`src/services/factory.py`, `src/improvers/ollama_improver.py`, `config.yaml`)
  - En la llamada actual se pasa `options={'temperature': ...}` pero **no** se fija un límite explícito de tokens/predicción (p. ej. `num_predict`) ni `num_ctx/num_thread` desde Python. (`src/improvers/ollama_improver.py`)
- El repositorio incluye un **benchmark** para Mistral con métricas de rendimiento:
  - `scripts/diagnostics/bench_llm.py` mide **TTFT**, **tokens/s** (throughput) y **pico de RAM** usando streaming.
- Los documentos del proyecto estiman para Mistral 7B Q4_K_M un uso de memoria alrededor de **~5.5–6 GB RAM** con `n_ctx=4096`, y recomiendan bajar `n_ctx` si la RAM es limitada. (`docs/tools/Mistral.md`, `docs/MistralTasks.md`)

### Lo que NO está en los adjuntos (y sería clave para concluir)

- Especificaciones reales del “PC normal” objetivo (CPU exacta, núcleos físicos, RAM, SSD/HDD, Windows/WSL, antivirus, plan de energía).
- Medidas reales del problema (TTFT, tokens/s, tiempo total por texto, uso de RAM/swap/pagefile, %CPU).
- Info del build/runtime (si `llama-cpp-python` está usando BLAS/AVX2/AVX512; configuración real de Ollama para Gemma).

---

## Hipótesis plausibles (con confianza) y cómo validarlas

1) **Se está generando demasiado texto (límite de tokens alto / mal acotado)**  
   - Confianza: **Alta** (Mistral: `max_tokens` puede llegar a ~526; Gemma: no hay límite explícito en el wrapper).  
   - Cómo validarlo:
     - Registrar por request: `input_tokens`, `output_tokens`, `max_tokens/num_predict` efectivo y tiempo.
     - Para Mistral: probar `max_tokens` 64/128/192 y comparar tiempo total sin pérdida de calidad perceptible.
     - Para Gemma/Ollama: fijar `num_predict` (p. ej. 128–256) y comparar.
   - Señal esperada: el tiempo cae casi linealmente con los tokens generados; la salida “corrigida” no necesita cientos de tokens.

2) **Backend CPU no está optimizado (sin BLAS o con flags CPU subóptimos)**  
   - Confianza: **Media–Alta** (típico en instalaciones con wheels genéricas).  
   - Cómo validarlo:
     - Ejecutar `python scripts/diagnostics/bench_llm.py` y anotar `tokens/s` y TTFT.
     - Inspeccionar info de compilación del runtime (según API disponible de `llama_cpp`) o, como mínimo, comparar rendimiento entre:
       - wheel precompilada “CPU optimizada” vs build con OpenBLAS/MKL.
   - Señal esperada: un build con BLAS suele mejorar throughput y/o TTFT de manera notable (especialmente en prompt-eval).

3) **`n_threads=os.cpu_count()` está sobre-paralelizando (usa hilos lógicos y degrada por contención)**  
   - Confianza: **Media**.  
   - Cómo validarlo:
     - Hacer un sweep con `n_threads` (p. ej. 2/4/6/8/physical_cores/logical_cores) midiendo `tokens/s` con `bench_llm.py`.
   - Señal esperada: existe un “punto óptimo” cercano a núcleos **físicos**; más hilos no siempre acelera.

4) **Presión de RAM (KV-cache grande + modelo) induce swapping/pagefile y cae el rendimiento**  
   - Confianza: **Alta** si los equipos son de **8 GB** o menos; **Media** si son 16 GB.  
   - Cómo validarlo:
     - Medir pico de RSS (ya lo hace `bench_llm.py`) y observar si el sistema usa swap/pagefile.
     - Probar `n_ctx` 1024/2048 y comparar TTFT + tokens/s + pico de RAM.
   - Señal esperada: al bajar `n_ctx`, baja el pico de RAM; si había swapping, la latencia mejora drásticamente.

5) **`use_mlock=True` empeora en máquinas “justas” (o no aporta) por presión de memoria**  
   - Confianza: **Media**.  
   - Cómo validarlo:
     - Comparar `use_mlock=True` vs `False` con `bench_llm.py`, y monitorizar swap/pagefile y tiempos.
   - Señal esperada: en RAM limitada, desactivar `mlock` evita presión extrema; en RAM holgada, puede mejorar estabilidad.

6) **`use_mmap=True` + almacenamiento lento (HDD / antivirus / WSL en `/mnt/c`) causa page-faults y TTFT alto**  
   - Confianza: **Media** (muy común en entornos educativos y/o cuando se prueba en WSL sobre disco Windows).  
   - Cómo validarlo:
     - Medir I/O y page faults durante inferencia.
     - Probar: mover el modelo a SSD/local (en WSL: a un path en ext4, no `/mnt/c`) y/o `use_mmap=False`.
   - Señal esperada: TTFT y estabilidad mejoran al eliminar I/O aleatorio y page faults.

7) **El coste fijo del pipeline (spaCy + LanguageTool x2) se suma a una inferencia ya lenta**  
   - Confianza: **Media**.  
   - Cómo validarlo:
     - Instrumentar tiempos por etapa: `t_spacy`, `t_lt_pre`, `t_llm`, `t_lt_post`.
     - Comparar con/ sin post-validación o con una validación más barata (muestreo / reglas reducidas).
   - Señal esperada: en textos cortos, LT+spaCy pueden ser una parte relevante del tiempo total.

8) **Ollama/Gemma está configurado con contexto/predicción por defecto demasiado altos para “corrección”**  
   - Confianza: **Media** (no se ve configuración explícita en el wrapper).  
   - Cómo validarlo:
     - Medir latencia con `num_ctx` bajo (1024–2048) y `num_predict` 128–256 en `options`.
   - Señal esperada: latencia baja sin afectar la tarea (no necesita contexto enorme).

9) **La UI no hace streaming: el usuario percibe “bloqueo” aunque el throughput sea razonable**  
   - Confianza: **Alta** (Mistral en UI usa llamada bloqueante; Ollama también se consume como respuesta completa).  
   - Cómo validarlo:
     - Implementar streaming (aunque sea parcial) y comparar “tiempo a primera señal” percibido.
   - Señal esperada: TTFT percibido cae, UX mejora incluso si el tiempo total cambia poco.

---

## Plan de diagnóstico (pasos, qué medir, cómo medir, qué esperar)

1) **Caracterizar hardware/software del equipo objetivo (por perfil)**
   - Medir: CPU (modelo), núcleos físicos/lógicos, RAM, tipo de disco (SSD/HDD), SO (Windows nativo vs WSL), plan de energía.
   - Cómo: inventario del centro (o scripts simples) + documentar 2–3 “clases” de PC (bajo/medio/alto).
   - Esperar: identificar rápidamente si 7B Q4 es viable o si hay que ir a 4B/3B.

2) **Medir baseline Mistral con el benchmark incluido**
   - Medir: TTFT, tokens/s, pico de RAM.
   - Cómo: `python scripts/diagnostics/bench_llm.py` (mismo modelo/config).
   - Esperar: números reproducibles para comparar cambios (threads, ctx, batch, mmap/mlock).

3) **Medir baseline Gemma/Ollama con una prueba equivalente**
   - Medir: TTFT y tokens/s (o al menos tiempo total + tokens generados).
   - Cómo: un script simple que llame a `ollama.chat(stream=True)` (o `ollama run`) con prompt fijo.
   - Esperar: ver si Gemma supera o no a Mistral en CPU en el hardware real.

4) **Perf por etapas del pipeline (cuello de botella real)**
   - Medir: `t_spacy`, `t_lt_pre`, `t_llm`, `t_lt_post`, `t_total`.
   - Cómo: instrumentación con `time.perf_counter()` en improvers (temporal) o `cProfile`.
   - Esperar: decidir si optimizar LLM (lo típico) o si LT domina en textos cortos.

5) **Sweep de `n_threads` (Mistral)**
   - Medir: tokens/s y %CPU.
   - Cómo: correr benchmark variando `n_threads` (por ejemplo 2/4/6/8/physical).
   - Esperar: encontrar el “sweet spot”; evitar usar todos los hilos lógicos si empeora.

6) **Sweep de `n_ctx` (Mistral + Gemma)**
   - Medir: pico de RAM, TTFT, tokens/s.
   - Cómo: probar 1024/2048/4096 (configurable por perfil).
   - Esperar: en PC con RAM limitada, `n_ctx` bajo evita swapping y mejora mucho.

7) **Probar `use_mmap` y ubicación del modelo**
   - Medir: TTFT, I/O de disco, page faults.
   - Cómo: mover modelo a SSD/local; en WSL, evitar `/mnt/c` para el `.gguf`.
   - Esperar: si el problema era I/O/page faults, TTFT cae y la generación se estabiliza.

8) **Acotar longitud de salida (Mistral/Gemma)**
   - Medir: tokens generados vs tiempo; tasa de “salida demasiado larga”.
   - Cómo: fijar límites (`max_tokens`/`num_predict`) y/o stop manual por ratio longitud salida/entrada.
   - Esperar: gran reducción del tiempo total en tareas de corrección (no requiere outputs largos).

9) **Verificar build/optimizaciones del backend**
   - Medir: diferencia de tokens/s tras cambiar wheel/build.
   - Cómo: comparar una instalación con BLAS (OpenBLAS/MKL) vs sin BLAS.
   - Esperar: mejoras claras en prompt-eval y throughput.

10) **Definir presets por perfil de PC (centro educativo)**
   - Medir: satisfacción de latencia objetivo (p. ej. <5–8 s por párrafo corto) y tasa de fallback al modo ligero.
   - Cómo: calibrar 2–3 configuraciones (Low/Medium/High) y fijar defaults.
   - Esperar: experiencia consistente en parque heterogéneo.

---

## Soluciones factibles (priorizadas por impacto vs esfuerzo)

### P0 — Alto impacto / Bajo esfuerzo (hacer primero)

- **Acotar tokens de salida**:
  - Mistral: bajar `max_tokens` (p. ej. 128–256) y basarlo en **tokens** de entrada (no palabras), con margen pequeño.
  - Gemma/Ollama: pasar `options={'num_predict': 128..256, 'temperature': ...}` y, si aplica, `num_ctx` bajo.
- **Reducir contexto** (`n_ctx`) para la tarea real:
  - Corrección suele necesitar **1024–2048**; 4096 aumenta KV-cache y riesgo de swapping.
- **Elegir `n_threads` por núcleos físicos** (o un valor conservador por defecto, configurable):
  - Evitar `os.cpu_count()` como “auto” universal.
- **Streaming en UI**:
  - Mistral: usar streaming (`stream=True`) y render incremental en Streamlit para reducir latencia percibida.
  - Gemma/Ollama: consumir streaming si está disponible.
- **Warm-up** del modelo al iniciar modo híbrido:
  - Ejecutar un prompt corto una vez para “calentar” páginas/cachés y reducir TTFT en el primer uso.

### P1 — Alto impacto / Esfuerzo medio

- **Asegurar backend optimizado en CPU (BLAS/AVX2)**:
  - Empaquetar/instalar `llama-cpp-python` o `llama.cpp` con BLAS (OpenBLAS/MKL) y flags adecuados al parque (típicamente AVX2).
- **Separar inferencia en un proceso servicio (llama.cpp server)**:
  - Ventajas: proceso persistente, menos bloqueo del UI, mejor control de threads/batch/ctx, posible concurrencia.
  - Encaja con la arquitectura sugerida en `docs/Conception French Version.md`.
- **Modelo más pequeño / más cuantizado para PCs “justos”**:
  - Mantener GGUF pero ofrecer variantes (p. ej. Q4_K_M como base; Q3 para low-end) o cambiar a un 4B/3B si el objetivo es latencia.

### P2 — Impacto medio / Esfuerzo medio–alto

- **Optimizar el pipeline para reducir llamadas caras**:
  - Evitar LT post-validación completa cuando la salida es corta y cumple guardrails simples (o hacer un check “rápido”).
  - Ejecutar LLM solo si LT detecta “casos difíciles” (gate por severidad/recalls).
- **KV-cache y memoria**:
  - Mantener KV-cache en FP16 (si aplica) y ajustar `n_ctx`.
  - Evaluar técnicas de KV-cache más compactas **solo si el backend lo soporta** y no degrada calidad.

---

## Recomendaciones específicas (resumen operativo)

### Cuantización / formato / backend

- **Formato**: mantener **GGUF** para CPU (es lo que ya usa Mistral en el repo).
- **Cuantización**:
  - Base sin GPU: **4-bit** (ej. Q4_*). Si RAM es crítica, evaluar **3-bit** con trade-off de calidad.
  - 8-bit suele mejorar calidad pero aumenta RAM y puede bajar velocidad en hardware limitado.
- **Backend**:
  - CPU-only: priorizar **llama.cpp / llama-cpp-python** (ya está integrado).
  - **vLLM**: típicamente orientado a GPU; en CPU suele no ser el camino más simple/eficiente para este caso.
  - **Transformers optimizados** (ONNX/OpenVINO/oneDNN) pueden ser opción si se acepta más complejidad de build/despliegue.

### Parámetros de ejecución (CPU-only)

- **Threads (`n_threads`)**: calibrar por hardware; punto de partida conservador:
  - PCs 4C/8T: 4–6 threads
  - PCs 6C/12T: 6–8 threads
  - Ajustar con benchmark (no asumir que “más = mejor”).
- **Batch** (`n_batch` en llama.cpp/llama-cpp-python): subirlo mejora prompt-eval pero usa más RAM; calibrar (128/256/512).
- **Contexto (`n_ctx`)**: 1024–2048 para corrección; 4096 solo si hay casos reales que lo necesitan.
- **KV-cache**: reducir `n_ctx` es la palanca principal para memoria; evitar swaps.
- **Streaming**: habilitarlo para mejorar TTFT percibido y permitir cortar temprano.

### Paralelización (qué sí / qué no)

- **Sí paralelizar**:
  - Peticiones independientes (si hay multiusuario) **solo si** hay recursos para ello y el backend lo permite.
  - Pre/post-proceso (spaCy/LT/diff) en paralelo con UI (no bloquear render), o en un worker.
- **No paralelizar** (o con retorno decreciente):
  - Una sola generación token-a-token no escala linealmente con más procesos: es secuencial a nivel de tokens; el paralelismo útil está dentro del backend (threads/BLAS) y en batching controlado.
  - Multiplicar instancias del modelo en RAM en PCs de 8–16 GB suele ser inviable.

---

## Tabla final (Problema → Evidencia esperada → Cómo confirmarlo → Solución → Impacto estimado)

| Problema | Evidencia esperada | Cómo confirmarlo | Solución | Impacto estimado |
|---|---|---|---|---|
| Salida demasiado larga (tokens) | Tiempo total crece con tokens generados; respuestas “verborreicas” | Log `output_tokens`/tiempo; bajar `max_tokens/num_predict` | Limitar `max_tokens` (Mistral) y `num_predict` (Ollama); stop manual por ratio salida/entrada | Alto |
| Backend CPU no optimizado | Tokens/s muy bajos vs esperado en ese CPU | `bench_llm.py` antes/después; comparar builds | Usar BLAS (OpenBLAS/MKL) y build AVX2; o `llama.cpp` binario optimizado | Alto |
| Hilos mal ajustados | %CPU alto pero tokens/s no mejora o empeora | Sweep `n_threads` con benchmark | Fijar `n_threads` cercano a núcleos físicos; preset por perfil | Medio–Alto |
| `n_ctx` demasiado grande | Pico de RAM alto; swapping/pagefile; TTFT sube | `bench_llm.py` + monitoreo RAM/swap; probar 1024/2048 | Bajar `n_ctx` (1024–2048) y/o dinámico según longitud | Alto (en 8 GB) |
| `use_mmap` + disco lento/WSL/antivirus | TTFT errático; I/O elevado; page faults | Monitoreo I/O; mover modelo a SSD/local; probar `use_mmap=False` | Ubicar modelos en SSD/local; evitar `/mnt/c` en WSL; ajustar `use_mmap` | Medio–Alto |
| `use_mlock` en equipos “justos” | Presión de memoria; el SO se vuelve lento | Comparar `mlock` on/off; mirar swap/pagefile | Hacer `mlock` configurable y desactivarlo en low-RAM | Medio |
| Overhead LT+spaCy (x2 LT) | `t_lt_pre + t_lt_post` comparable a `t_llm` en textos cortos | Instrumentación por etapas | Reducir/optimizar validación post; gatear LLM solo en casos difíciles | Medio |
| Gemma/Ollama sin límites de inferencia | Latencia variable; outputs largos por default | Fijar `num_predict/num_ctx/num_thread` y comparar | Pasar options explícitas a Ollama y streaming | Medio–Alto |
| UI sin streaming | UX “congelada” aunque TTFT real sea aceptable | Implementar streaming y medir TTFT percibido | Streaming incremental + botón “cancelar” | Medio (UX) |


import time, psutil, os, sys
from pathlib import Path
from llama_cpp import Llama

# Benchmark script to measure TTFT, throughput, and peak memory for a local LLM.
# Add src to path so imports resolve when the script is run directly.
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.utils.config import load_config

# Load LLM configuration from the shared config file.
cfg = load_config()
model_name = cfg['llm']['model']
base_name = model_name.replace('-7b-q4', '').replace('-q4', '')
model_config = cfg['llm'][base_name]
MODEL = Path(cfg['llm']['models_dir']) / model_config['filename']
N_CTX = model_config['n_ctx']
MAX_TOKENS = model_config['max_tokens']
TEMPERATURE = model_config['temperature']

# Ensure the model file exists before starting the benchmark.
if not MODEL.exists():
    print(f"❌ Error: Model not found at {MODEL}")
    print("\nPlease run: python scripts/download_mistral.py")
    sys.exit(1)

# Log the main parameters to make runs reproducible.
print(f"{'='*70}")
print(f"LLM BENCHMARK - {model_name}")
print(f"{'='*70}")
print(f"Model: {MODEL.name}")
print(f"Context: {N_CTX}")
print(f"Max tokens: {MAX_TOKENS}")
print(f"Temperature: {TEMPERATURE}")
print(f"Threads: {os.cpu_count()}")
print(f"{'='*70}\n")

# Initialize the model with the same thread and GPU settings across runs.
llm = Llama(model_path=str(MODEL), n_ctx=N_CTX, n_threads=os.cpu_count(), n_gpu_layers=0, use_mlock=True, verbose=False)

# Use a longer, repeatable prompt that exercises summarization while producing enough tokens.
prompt = "[INST] Write a ~150 word summary in French that explains causes, impacts, and mitigation ideas for this climate resilience story so a curious adult can follow: Les températures mondiales augmentent, les océans se réchauffent, et les villes côtières voient les marées monter plus haut chaque année. Les habitants s'inquiètent des tempêtes plus violentes, des infrastructures vieillissantes et de la nécessité d'investir dans des solutions durables pour protéger leurs quartiers. [/INST]"

proc = psutil.Process(os.getpid())
peak_rss = proc.memory_info().rss

# Track wall-clock time and TTFT for the streaming response.
start = time.time()
ttft = None
out_text = []

# Generate tokens and measure TTFT/throughput while sampling memory usage.
gen_start = time.time()
for chunk in llm.create_completion(prompt=prompt, max_tokens=MAX_TOKENS, temperature=TEMPERATURE, top_p=0.85, stream=True):
    if ttft is None:
        ttft = time.time() - start
    out_text.append(chunk["choices"][0]["text"])
    # Sample RSS each chunk to capture the peak memory usage.
    rss = proc.memory_info().rss
    if rss > peak_rss:
        peak_rss = rss

end = time.time()
gen_time = end - gen_start
text = "".join(out_text)
tokens = len(llm.tokenize(text.encode("utf-8")))
tps = tokens / gen_time if gen_time > 0 else 0.0

print(f"\n{'='*70}")
print("RESULTS")
print(f"{'='*70}")
print(f"TTFT (Time to First Token): {ttft:.2f}s")
print(f"Generation speed: {tps:.1f} tokens/s")
print(f"Peak RAM: {peak_rss/1e9:.2f} GB")
print(f"Tokens generated: {tokens}")
print(f"Total time: {end - start:.2f}s")
print(f"{'='*70}\n")

# TODO

Open work found while building [business-rules.md](business-rules.md). Nothing here has
been fixed — this is a queue, not a changelog.

[completion-plan.md](completion-plan.md) schedules this queue: the decisions below are
Phase 0, TODO-1 to TODO-3 are Phase 2, and TODO-4 to TODO-8 are Phase 4.

Two populations only:

1. **Code defects** — the code does something other than what it says it does. Bounded work.
2. **Decisions** — the archived documents contradict each other, and a number has to be
   picked before the affected rule can be enforced at all.

**Not in this list:** the 28 documented rules with no implementation (intervention levels,
the QA corpus, the accessibility controls, the automatic Gemma fallback). Those are product
decisions about what to build, not defects. They stay catalogued in
[business-rules.md](business-rules.md); if one is chosen, it moves here.

---

## Code defects

### TODO-1 · Degradation guardrail can accept a worse rewrite — **High**

`src/improvers/llm_improver.py:270`

The hybrid pipeline's only post-validation check compares error counts before and after
the LLM pass. Both counts are taken from the **capped hint list**, not from the raw
LanguageTool matches:

```
error_count_before = len(lt_hints)        # line 204, hints capped at max(5, n*0.1)
error_count_after  = len(lt_hints_after)  # line 260, same cap
if error_count_after > error_count_before: # line 270
```

Because `_extract_lt_hints` truncates at `max(5, len(matches) * 0.1)` (line 126), both
sides saturate. A text with 10 errors before and 50 after yields `5 > 5` → false, and the
degraded rewrite is **accepted and returned to the user**. The raw count is available on
line 202 but commented out.

`ollama_improver.py` does not have this bug: it compares raw counts (lines 68 and 91).

Affects rule D2, and makes H12's untested degradation check untestable as written.

### TODO-2 · Whitelist guardrail disabled, with a comment that misstates why — **High**

`src/improvers/lt_improver.py:174`

`_is_whitelist_change` (line 82) is written and correct, and nothing calls it. The comment
in its place lists the guardrails supposedly compensating for it:

```
# - No new entities (checked via spaCy NER)
```

There is no such check. spaCy is used for *masking* before correction, not for validating
the result, and `validate_no_new_entities` is a `pass` stub. Two of the four compensating
guardrails the comment claims do not exist.

The disabling itself may well be correct — the comment notes the whitelist blocked
legitimate corrections like "sui"→"suis". The defect is the justification, which will
survive the next code review as if it were protection.

Affects rule A11.

### TODO-3 · LanguageTool category filter is structurally a no-op — **Medium-High**

`src/improvers/lt_improver.py:10-11`

```python
_SAFE_CATEGORIES: set[str] = set()
_BLOCK_CATEGORIES = set()
```

With both sets empty, `_safe_by_category` (line 61) returns `True` for every match: the
block loop finds nothing, and the `if not _SAFE_CATEGORIES` short-circuit allows all. The
call site at line 168 reads like category filtering and filters nothing.

Same failure mode as TODO-2: apparent protection.

Affects rule C8.

### TODO-4 · Configured temperature is silently discarded — **Medium**

`src/improvers/llm_improver.py:231`

`config.yaml:28` sets `temperature: 0.3`. The value is read and stored on line 51, then
never used: the generation call hardcodes `temperature=0.1`. Tuning the config has no
effect. The hardcoded value is more conservative, so output quality is not at risk — the
configuration is.

Affects rule G5 and contradiction I-8.

### TODO-5 · Ollama call has no timeout — **Medium**

`src/improvers/ollama_improver.py:78`

`config.yaml:32` declares `timeout: 120`. The call passes `options={'temperature': ...}`
and nothing else: `timeout`, `num_predict` and `num_ctx` never reach Ollama. An
unresponsive Ollama daemon blocks the Streamlit thread with no bound.

Affects rule G6.

### TODO-6 · Degradation reverts to the wrong target — **Medium**

`src/improvers/llm_improver.py:275`, `src/improvers/ollama_improver.py:95`

`docs/archive/Conception French Version.md:78` and the client deliverable (`.tex:92`)
specify that a failed LLM pass falls back to the **LanguageTool output**. Both improvers
fall back to the masked *input*, discarding the LT pre-pass corrections that were already
validated. The user gets less than the light mode would have produced.

Affects rules D2 and C9, and contradiction I-6.

### TODO-7 · Local-LLM resource settings ignore the project's own analysis — **Low**

`src/improvers/llm_improver.py:57,59` and `config.yaml:26`

`docs/archive/porposals.md` analysed the runtime and recommended physical-core thread
counts rather than `os.cpu_count()` (line 220), `n_ctx` of 1024–2048 rather than 4096
(line 174), and warned that `use_mlock=True` is harmful on low-RAM machines (line 249).
None was applied. Low severity because it degrades speed, not correctness — but it is the
difference between the hybrid mode being usable or not on the 6 GB machines the docs
target.

Affects rules G3, G8, G9.

### TODO-8 · Misleading comment on the hint cap — **Low**

`src/improvers/llm_improver.py:128`

The inline comment says `# Limit to top 5 errors`; the expression is
`max(5, len(matches) * 0.1)`, which exceeds 5 on any text with more than 50 matches.
Affects rule D4. Contributing cause of TODO-1.

---

## Decisions needed

Each is a contradiction between archived documents. None can be resolved by reading the
code, because in most cases the code implements neither option.

| # | Decision | Options on the table |
|---|---|---|
| I-1 | Novelty ratio threshold | 10–15%, 10–12%, or block above 15% — three documents, three numbers |
| I-2 | **Is reordering allowed?** | Design docs and `README.md` say yes; the shipped prompt says no. The prompt currently wins |
| I-3 | **Is sentence splitting allowed?** | Same split. The shipped prompt dropped the instruction entirely |
| I-4 | **Is Hunspell part of this product?** | `README.md` advertises it; the design recommended dropping it; no code or dependency exists |
| I-6 | Degradation fallback target | LT output (spec) or masked input (code). See TODO-6 |
| I-7 | `max_tokens` | 512 or 526 |
| I-9 | Stated RAM requirement | ≤4 GB, 5.5–6 GB, or ≥6 GB — the same document says two of the three |
| I-10 | QA corpus size | 20–30 sentences or 25–40 texts |
| I-11 | `n_ctx` | 4096 (current) or 1024–2048 (the project's own recommendation) |
| I-12 | GGUF source and filename casing | `TheBloke` or `bartowski`; two spellings of the filename. The build uses bartowski |

I-2, I-3 and I-4 are the ones that matter: they are public claims in `README.md` about
what the product does, and the product does not do them.

I-5, I-8, I-13, I-14 and I-15 are not listed here — they are stale statements in archived
documents rather than open questions, and they are recorded in
[business-rules.md](business-rules.md#i-contradictions-between-sources).

---

## One thing that is neither

`README.md` advertises five accessibility features that do not exist (E1–E5: dyslexia
fonts, adjustable font size, adjustable line spacing, high-contrast mode, focus mode) and
names Hunspell as part of the engine. The repository is public.

This is not a code defect and not a documentation contradiction — it is a claim about a
shipped product. It needs a decision that is not on either list above: correct the README,
or build the features.

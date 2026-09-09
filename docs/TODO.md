# TODO

Open work found while building [business-rules.md](business-rules.md). A queue, not a
changelog: entries move to **Fixed** at the bottom when they are closed, with a one-line
note of how.

[completion-plan.md](completion-plan.md) schedules this queue: the decisions below were
Phase 0; TODO-2 is Phase 2; TODO-4 to TODO-8 and TODO-11 are Phase 4.
TODO-9 and TODO-10 were fixed on 2026-09-08.

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
legitimate corrections like "sui"→"suis".

**Partly resolved 2026-09-08**: the false justification is gone. The comment now lists
the guards that actually run and states plainly that entity masking does not validate
the result and that `_safe_by_category` is inert. What remains open is the decision
itself — keep the whitelist disabled, or repair and re-enable it.

Affects rule A11.

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

### TODO-11 · LanguageTool rewrites adjacent corrupted words — **Medium**

Found by the QA corpus, text `t24`. Two injected errors landing on neighbouring words:

```
IN : Il m'a montrré commen changer une chambre à air.
OUT: Il m'a m'entre nommer-en changer une chambre à air.
```

`_stays_close_to_the_original` blocks a rewrite when LanguageTool proposes it as one
replacement — it stops "kompliqué" becoming "complice" in the same text. Here LanguageTool
emits two *separate* matches, each individually within the edit budget, whose combined
result is gibberish.

Deliberately not fixed by tightening the budget further: that would start refusing
legitimate fixes like "preske" -> "presque", which sits at the same distance. A real fix
needs to judge adjacent replacements together rather than one at a time, or to give up on a
span the spell checker cannot resolve confidently.

The metrics still pass — H3 is 0 and H4 is above target — because the rest of the text is
corrected. But a reader would see this output and conclude the tool is broken, which is a
different and worse failure than a missed correction.

### TODO-8 · Misleading comment on the hint cap — **Low**

`src/improvers/llm_improver.py:128`

The inline comment says `# Limit to top 5 errors`; the expression is
`max(5, len(matches) * 0.1)`, which exceeds 5 on any text with more than 50 matches.
Affects rule D4. Contributing cause of TODO-1.

---

## Decisions taken

Each was a contradiction between archived documents. All ten were approved on 2026-09-08;
the recommendations and their reasoning are in
[completion-plan.md](completion-plan.md#decisions-awaiting-approval). Recorded here so the
implementation phases have the numbers to hand.

| # | Decision | Resolved as | Lands in |
|---|---|---|---|
| I-1 | Novelty ratio threshold | **12%**, configurable | Phase 2 |
| I-2 | Is reordering allowed? | **No** | Phase 2 |
| I-3 | Is sentence splitting allowed? | **Yes, bounded**: LT-proposed or over threshold, at most 2 parts, no invented connectors | Phase 3 |
| I-4 | Is Hunspell part of this product? | **No** — removed from `README.md` | Done |
| I-6 | Degradation fallback target | **LanguageTool output** | Phase 4 (TODO-6) |
| I-7 | `max_tokens` | **512** | Phase 4 |
| I-9 | Stated RAM requirement | **4 GB light, 8 GB recommended for hybrid** | Phase 4 |
| I-10 | QA corpus size | **30 texts** | Done (`src/qa/corpus.py`) |
| I-11 | `n_ctx` | **2048**, measured before and after | Phase 4 (TODO-7) |
| I-12 | GGUF source and filename casing | **bartowski, pinned to an immutable revision** | Phase 4 |

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

---

## Fixed

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

**Fixed 2026-09-09**: both sides now count raw LanguageTool matches
(`src/improvers/llm_improver.py`). The commented-out correct line was restored and the
hint list is used only for prompting.

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

**Resolved 2026-09-09** by removal. The two empty sets and `_safe_by_category` are gone;
rule C8 is now realised by `_BLOCK_RULES`, which blocks by rule id. Category granularity
proved too coarse: PUNCTUATION as a whole carries fixes this product wants and only one
of its rules is harmful.

### TODO-9 · LanguageTool substitutes a proper noun for a garbled word — **High**

Found by the first QA corpus run (`src/qa/`), text `t17`.

The corpus injected a letter inversion turning "douze" into "duoze". LanguageTool's spell
checker replaced it with **"Eauze"** — a real French commune. The engine invented a place
name where the user had written a misspelt number word.

`_does_not_add_digits` (`src/improvers/lt_improver.py:73`) guards against introducing
digits. There is no equivalent guard for proper nouns, even though A4 requires one and
`validate_no_new_propn` is a `pass` stub.

This is the exact failure mode the no-additions policy exists to prevent, and it happens in
**light mode**, without any LLM involved.

**Fixed 2026-09-08** by `_does_not_introduce_proper_noun` in `src/improvers/lt_improver.py`:
a replacement may not introduce a capitalised segment absent from the original, while
capitalising a word the user already wrote stays allowed. The guard splits on apostrophes
and hyphens, because LanguageTool's actual suggestion was the elided `d'Eauze`, whose
leading letter is lowercase.

Affects rules A2, A4, H3, H9.

### TODO-10 · A deliberate "`..`" blank is filled in — **High**

Found by the first QA corpus run, text `t29`, which encodes client acceptance criterion B1
from the `.tex` deliverable verbatim.

LanguageTool's `DOUBLE_PUNCTUATION` rule replaces "`..`" with "`.`", destroying a blank the
user left on purpose. The client acceptance test is "l'année de l'indépendance des
États-Unis est le .. de .." must come back **still incomplete**; today it does not.

**Fixed 2026-09-08** by `_BLOCK_RULES` in `src/improvers/lt_improver.py`. Blocked by rule
id rather than by category: PUNCTUATION as a whole carries useful fixes and only this rule
is harmful.

Affects rules B1, H15, and client acceptance.

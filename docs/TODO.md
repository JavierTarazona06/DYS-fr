# TODO

Open work found while building [business-rules.md](business-rules.md). A queue, not a
changelog: entries move to **Fixed** at the bottom when they are closed, with a one-line
note of how.

[completion-plan.md](completion-plan.md) schedules this queue: the decisions below were
Phase 0; TODO-2 is Phase 2; TODO-4 to TODO-8 and TODO-11 are Phase 4.
TODO-9 and TODO-10 were fixed on 2026-09-08. TODO-12 to TODO-17 were found by the full
reinstall test of 2026-09-17.

Five sections:

1. **Code defects** — the code does something other than what it says it does. Bounded work.
2. **Documentation drift** — a document states something about the code that is no longer
   true. Cheap to fix, and expensive to leave: agents and reviewers act on it.
3. **Release and delivery** — what stands between the branch and a client install.
4. **Remaining plan work** — a checklist of the unbuilt features, so the whole backlog can be
   worked from one page. [completion-plan.md](completion-plan.md) remains the specification;
   [business-rules.md](business-rules.md) remains the inventory.
5. **Decisions** — the archived documents contradicted each other; all are now taken.

## Last full verification — 2026-09-17

Rebuilt the installer from `784507d`, uninstalled the 2026-09-08 build, reinstalled.

| Check | Result |
|---|---|
| `build.ps1 -Channel installer -IncludeAiRuntime -FastCompression` | Pass. 572 MB in 8 min, unsigned, SHA-256 `C2FA5F940066BB426CE6FED73863D32F1277F9FBD1B105AB157D7F6214689D92` |
| `unins000.exe /VERYSILENT /KEEPDATA` | Pass. Install dir, registry entry, Start Menu, `logs`, `run` and legacy `spacy_models` removed; `models` kept |
| `DYS-fr-Setup-0.1.0.exe /VERYSILENT` | Pass. Exit 0 in 82 s, 1.15 GB installed |
| `packaging/windows/smoke_test.py` | Pass. UI 2.7 s, LanguageTool 3.2 s, install dir unchanged |
| `pytest tests/ --ignore=tests/test_llm_mistral.py` | Pass. 193 passed |
| `pytest tests/test_llm_mistral.py` | **Fail**, 5/6. `test_mistral_no_hallucination`, see TODO-14 |
| Correction in the installed app | Works, with the embedded JRE. Surfaced TODO-12, TODO-13, TODO-15, TODO-16, TODO-17 |

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

**Reproduced 2026-09-17** on the installed build, identical output.

**Half fixed 2026-09-17** by TODO-13: "montrré" -> "m'entre" was a split elision, and the
engine now takes "montré" instead. The text reads "Il m'a montré nommes-en changer". The
remaining half is a hyphen split, "commen" -> "nommes-en", the same shape as TODO-13 with a
hyphen instead of an apostrophe. Extending that guard to hyphens is the obvious next step,
but not a sufficient one: in `t20`, "rendon" -> "rend-on" keeps the user's letters exactly
and is still wrong ("rendons").

### TODO-8 · Misleading comment on the hint cap — **Low**

`src/improvers/llm_improver.py:128`

The inline comment says `# Limit to top 5 errors`; the expression is
`max(5, len(matches) * 0.1)`, which exceeds 5 on any text with more than 50 matches.
Affects rule D4. Contributing cause of TODO-1.

### TODO-14 · Hybrid mode can delete words, and nothing checks for it — **High**

`src/guardrails/policy.py:133` (`should_accept_correction`)

```
IN : Je sui aller au magasin.
OUT: Je suis au magasin.
```

`tests/test_llm_mistral.py:176` (`test_mistral_no_hallucination`) fails on this. The verb is
gone and the sentence now says something else. Every guard in `policy.py` looks for what the
output **adds** — entities, numbers, proper nouns, new tokens, neologisms. A deletion passes
all of them, and the LanguageTool degradation check accepts it too, since the shorter
sentence has fewer errors.

The no-additions policy is the product's central commitment, but its purpose is "no change
of meaning", and removal changes meaning as surely as insertion. Needs a symmetric check:
the input's content words (nouns, verbs, adjectives, adverbs) must survive into the output,
allowing for spelling correction with the same edit tolerance the novelty guard uses.

Affects rules A1, A13 and H12. Light mode is not affected: LanguageTool replacements do not
drop words.

### TODO-15 · Homophone "corrections" that change the grammatical role — **Medium**

```
IN : Elle voulait partir, mes la caissiere a fermer la caise.
OUT: Elle voulait partir, mets la caissière à fermer la caisse.
```

Two LanguageTool rules each swap a homophone for another part of speech. `MAIS_MES` turns
the conjunction the user meant ("mais") into the verb "mets"; `A_INFINITIF` turns the
auxiliary "a" into the preposition "à", when the intended fix was "a fermé". Both results
read as grammatical French and mean something the user did not write, which a dyslexic
reader is the least equipped to notice.

Rule C4 allows homophone swaps only when the grammatical role is unchanged; it has no
implementation. A first step that needs no tagging: add the rules whose suggestions change
the part of speech to `_BLOCK_RULES`, and measure H4 before and after.

Affects rules C4 and A1.

### TODO-16 · A deliberate "`..`" blank capitalises the next word — **Low**

`src/improvers/lt_improver.py:21` (`_BLOCK_RULES`)

```
IN : L'année de l'indépendance des États-Unis est le .. de ..
OUT: L'année de l'indépendance des États-Unis est le .. De ..
```

TODO-10 kept the blank intact, but `UPPERCASE_SENTENCE_START` reads "`..`" as the end of a
sentence and capitalises "de". The text stays incomplete, so B1 holds, but the client's own
acceptance sentence comes back altered in a way nobody asked for. Blocking the rule outright would
lose legitimate capitalisation fixes; it should be skipped only when the preceding token is
the blank.

Affects rules B1 and H15.

### TODO-17 · Streamlit's "Deploy" button is shown in the packaged app — **Low**

`src/runtime/launcher.py:129-134`

The launcher disables telemetry and development mode, but not the toolbar, so the offline
desktop app shows a "Deploy" button that leads to Streamlit Community Cloud. It needs a
network connection, means nothing to a user of this product, and is one more distraction in
an interface built for dyslexic readers. `--client.toolbarMode=minimal` (supported by the
pinned Streamlit 1.51) removes it. Focus mode already hides it.

Affects rule E8.

---

## Documentation drift

Found during the 2026-09-17 review. Each is a false statement in a document that people
and agents act on.

- **DOC-1 · `AGENTS.md` describes the guardrail layer as stubs.** "Rules that matter" says
  `policy.py` is unimplemented stubs, `novelty.py` and `numbers_date.py` are empty, and
  nothing calls `should_accept_correction`. All false since `b5789ab`. It is the first
  file every agent reads, and it tells them the safety layer does not run.
- **DOC-2 · `README.md` marks built features as unbuilt.** 🚧 still sits on adjustable
  font size, line spacing and focus mode (built in phase 3a), on the validation layer
  ("not yet wired in") and the QA corpus (phases 1-2), and says no-additions is "enforced
  only by entity masking". Only E1 (fonts) and E4 (high contrast) are still unbuilt.
- **DOC-3 · `business-rules.md` rows not updated after phases 1 and 2.** A1 says "Only
  entity masking"; A3 says `numbers_date.py` is empty; H3 says "no metric is computed"; H12
  calls the degradation check defective (TODO-1, fixed); H13 says no test touches
  `_token_delta_ok` or `_does_not_add_digits` and cites the removed `_is_whitelist_change`;
  H1 and H4 are "Not implemented" although `src/qa/` measures them. Section J was updated on
  2026-09-09; these rows were not.
- **DOC-4 · TODO-2 is filed as an open defect but is resolved.** This file says "partly
  resolved", `completion-plan.md` says "resolved by removal", `business-rules.md` A11 says
  "Superseded", and `_is_whitelist_change` no longer exists. Move it to **Fixed**.

DOC-5, the completion plan claiming the "depui" rewrite was stopped, was corrected with
TODO-13 on 2026-09-17.

---

## Release and delivery

- **REL-1 · Nothing is pushed or merged.** `feature/windows-distribution-final-touches` is
  8 commits ahead of its remote and 81 ahead of `main`, with no pull request.
- **REL-2 · The installer is unsigned.** SmartScreen will warn every client. Blocked on two
  facts only the project owners have — whether there is a legal entity, and whether the
  delivery is commercial. Options and costs:
  [completion-plan.md](completion-plan.md#appendix--code-signing-deferred).
- **REL-3 · No release build exists.** Every recent build used `-FastCompression` (572 MB).
  The full-compression build takes about 8 hours for 507 MB; schedule it, do not start it
  on a delivery day.
- **REL-4 · The manual half of the release checklist has not been run.** The 2026-09-17
  test was a silent reinstall on the development machine. Still unverified, per
  [windows_release_checklist.md](windows_release_checklist.md): a clean VM, a standard user,
  the network disabled, port 8501 occupied, re-running setup with the app open, no console
  flash, `DYS-fr-runtime.exe` not elevated, the interactive uninstall prompt, and the model
  download with cancel, resume and hybrid mode without restart.
- **REL-5 · Reading-comfort settings are unverified on the installed build.** The CSS is
  live (line height 1.6 × 16 px measured in the installed app), but it was not confirmed
  that moving a slider writes `%LOCALAPPDATA%\DYS-fr\config.yaml` and survives a restart.
  Browser automation could not drive the slider; check by hand.

---

## Remaining plan work

Specified in [completion-plan.md](completion-plan.md); listed here so the backlog is on one
page. Tick them off here and record the detail there.

- [ ] **E1** — dyslexia fonts: Lexend, Atkinson Hyperlegible, OpenDyslexic (phase 3b; needs a
      frozen-build round trip for static serving)
- [ ] **E4** — high-contrast mode (phase 3c)
- [ ] **C10** — intervention levels Fidèle / Équilibré / Plus simple (phase 3)
- [ ] **C2 / I-3** — bounded sentence splitting; H6 readability cannot improve without it
- [ ] **TODO-4 to TODO-8** — hybrid robustness (phase 4)
- [ ] **D3** — automatic Gemma fallback with hardware detection; `src/utils/hw.py` does not
      exist (phase 4)
- [ ] **I-7** — `max_tokens: 512`; `config.yaml` still says 526
- [ ] **I-11** — `n_ctx: 2048`; `config.yaml` still says 4096 (with TODO-7)
- [ ] **I-12** — pin the GGUF to an immutable revision; `config.yaml:31` and
      `packaging/windows/build.ps1:15` still use `/resolve/main/`
- [ ] **E9, E10, C11, D5, G1, G2, H8, H10, H11** — smaller rules, unimplemented or partial;
      see [business-rules.md](business-rules.md)
- [ ] **H7** — study with 6-8 dyslexic users. Not engineering work, but a client obligation

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

## One thing that was neither

`README.md` advertised five accessibility features that did not exist (E1–E5) and named
Hunspell as part of the engine. Decided 2026-09-08: build the features and mark them 🚧 until
then, and drop Hunspell (I-4). Three of the five now exist; the README has not caught up,
which is DOC-2.

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

### TODO-12 · The user's text is written to the log file by default — **High**

Found by the reinstall test of 2026-09-17.

`src/improvers/lt_improver.py:27`

```python
_DEBUG_FILTER = os.getenv("LT_DEBUG_FILTER", "1").lower() in {...}
```

The filter trace defaulted to **on**. In the frozen build `print()` is redirected into
`%LOCALAPPDATA%\DYS-fr\logs\dys-fr.log` (`src/utils/logging_setup.py`), so every correction
wrote fragments of what the user typed to disk: `orig='jai' repl="j'ai"`, LanguageTool's
messages quoting the user's words, and `rejected_result reason=...`, which lists the words
a guardrail refused. One correction in the installed app produced 54 such lines.

The sidebar tells the user their sensitive data is protected, and the product exists for
people correcting personal writing. Nothing left the machine, so F1 held, but a plain-text
copy of the user's text persisting in a log they do not know about is exactly what that
promise rules out. `languagetool.log` is clean: it records character counts only.

Affects rule D5, which describes the trace as an opt-in toggle.

**Fixed 2026-09-17**: the trace is now opt-in. `_debug_filter_enabled` defaults to off and
`LT_DEBUG_FILTER=1` still turns it on for development; tested in
`tests/test_lt_guardrails.py`. Verified end to end: correcting four texts through the real
engine with the variable unset prints nothing. The hybrid improvers were already clean —
their text-bearing output sits behind `debug=`, which `app.py` never sets.

Two things the fix does not reach. The 0.1.0 installer built on 2026-09-17 predates it, so
rebuild before shipping. And logs already written on a machine keep their text until the
rotating handler overwrites them (2 MB × 4) or the app is uninstalled, which always deletes
`logs\`.

### TODO-13 · "depui" becomes "d'appui" in light mode — **High**

Found by the reinstall test of 2026-09-17.

`src/improvers/lt_improver.py` (first suggestion only; `_stays_close_to_the_original`)

```
IN : Il habite ici depui longtemps.
OUT: Il habite ici d'appui longtemps.
```

A dropped final letter is one of the most common dyslexic errors, and the output was a
different word that changed the sentence. [completion-plan.md](completion-plan.md) described
this exact rewrite as the one the span-level guard was built to stop; it was not stopped.
`tests/test_lt_guardrails.py` asserted that it passed, as a "known limitation", and no TODO
entry recorded it.

Distance alone cannot catch it — two edits on a five-letter word, same as "preske" ->
"presque". But LanguageTool offers the right answer, `FR_SPELLING_RULE` suggesting
`["d'appui", "d'étui", "d'époi", "depuis"]`, and the engine only ever looked at the first.

Affects rules A1, A5 and H4.

**Fixed 2026-09-17**, in two parts.

`_does_not_elide_into_another_word` refuses a replacement that adds an apostrophe and changes
the user's letters. "jai" -> "j'ai", "sil" -> "s'il" and "lecole" -> "l'école" keep every
letter and stay allowed. Every elision-adding replacement the corpus produced that changed
letters was wrong: "d'appui", "d'ans" for "daans", "m'entre" for "montrré", "l'écope" for
"lecole", "t'acte" for "tantte". Known cost: an elision fix that also needs a spelling fix
("lecol" -> "l'école") is left alone.

`_choose_replacement` then walks up to four suggestions down LanguageTool's list, but only
past refusals that mean LanguageTool reached for a different kind of word — a split elision
or an invented proper noun. Any other refusal still ends the search. Walking past every
refusal was measured first and rejected: it turned "quil" into "qui", "mangéée" into
"mangées", and let "Il fiat chaud" become "Il a fiat chaud". Six suggestions
instead of four reached "Lue" for "Luer".

Guard alone would have been the wrong stopping point: H4 fell to 79.6%, because LanguageTool
does not flag "d'appui" and the metric had been rewarding the wrong fix.

| Corpus | Before H4 | After H4 | H3 before/after |
|---|---|---|---|
| default seed | 82.8% (93 → 16) | **87.1%** (93 → 12) | 0 / 0 |
| seed 7 | 86.6% (97 → 13) | 86.6% (97 → 13) | 0 / 0 |
| seed 42 | 76.5% (98 → 23) | 78.6% (98 → 21) | 0 / 0 |

Across the three corpora and 19 probe sentences, 11 texts and 6 probes changed, every one
for the better: "depuis" 6 times, "douze" 3, "dans" 3, "montré" 2, and "l'école", "devant",
"tante" and "préfère" once each. None changed for the worse. Adversarial checks pass on all
three corpora. Seed 42 sits below target before and after, so that is not a
regression. 17 unit tests added.

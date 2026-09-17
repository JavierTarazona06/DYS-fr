# Business Rules Baseline

What DYS-fr actually enforces today, rule by rule, against what its documentation claimed.

This file replaces the conception documents now in [archive/](archive/README.md). Those
were written in October–November 2025; implementation continued until April 2026 without
updating them, and they contradict each other in fifteen places (section I). This document
is the current baseline: where a rule and the code disagree, **the code column is the
truth about the product**, and the source column records what was promised.

Nothing here has been fixed. This is an inventory, not a change. Open work is in
[TODO.md](TODO.md).

## How to read the status column

| Status | Meaning |
|---|---|
| **Implemented** | Code enforces the rule |
| **Implemented differently** | Enforced, by a different mechanism than the rule describes |
| **Superseded** | Replaced by another rule or decision that covers its intent |
| **Partial** | Enforced in some paths only, or materially weaker than stated |
| **Prompt-only** | Stated in the LLM prompt; no programmatic check. A model may ignore it |
| **Disabled** | The code exists and works, but nothing calls it |
| **Dead code** | The code runs but is structurally a no-op |
| **Not implemented** | No code corresponds to the rule |
| **Not applied / Not enforced** | A setting or analysis exists but the code does not follow it |
| **Not met** | Measured, and the measurement falls short |
| **N/A** | Not a software rule (project management, human study) |

Source paths are relative to the repository root. Line numbers were re-verified against the
working tree at commit `f60ceb9`; they drift as files grow, so re-check before quoting.

---

## A. No-additions policy

The core safety promise: a correction may fix form, never add content.

| # | Rule | Source | Status | Where |
|---|---|---|---|---|
| A1 | Return a corrected version **without adding new information** | `docs/archive/Conception French Version.md:6`, `README.md:16`, `.tex:45` | Partial | The final gate `should_accept_correction` (`src/guardrails/policy.py`) runs in all three improvers: no new entities, proper nouns, numbers or dates, neologisms, lost words, and a novelty ratio of at most 12%. LanguageTool replacements are also filtered one by one (`src/improvers/lt_improver.py`). Partial because the novelty check is a ratio, and changes carried only by function words are not counted |
| A2 | Output entities must be a subset of input entities: `NER(out) ⊆ NER(in)` | `docs/archive/Conception French Version.md:69`, `docs/archive/Moteur DYS fr.md:31` | **Implemented** | `src/guardrails/policy.py`, wired into all three improvers via `should_accept_correction`; tolerant of spelling corrections so it does not reject the product's own work |
| A3 | Output numbers/dates must be a subset of input numbers/dates | `docs/archive/Conception French Version.md:69`, `docs/archive/Moteur DYS fr.md:31` | **Implemented** | `validate_no_new_numbers_dates` in the final gate, all three improvers, backed by `src/guardrails/numbers_date.py`. Counts as a multiset, so a *changed* digit is a new one. Also `_does_not_add_digits` per replacement in light mode |
| A4 | New or modified proper nouns (PROPN) must be blocked | `docs/archive/Conception French Version.md:69`, `docs/archive/Moteur DYS fr.md:32` | **Implemented** | `validate_no_new_propn` in the final gate, all three improvers, and `_does_not_introduce_proper_noun` per replacement in light mode (TODO-9). Known defect: the light-mode guard misreads capitals the user typed (TODO-19) |
| A5 | No new meaning-bearing words (nouns, verbs, adjectives, adverbs) | `docs/Ideas prompt.txt:32` | Partial | Strict in light mode: `_does_not_insert_words` refuses inserting a word (TODO-18 notes a one-letter gap). In hybrid mode only bounded, by the 12% novelty ratio and the neologism check |
| A6 | New discourse connectors ("En effet", "Par conséquent") must be blocked | `docs/archive/Moteur DYS fr.md:17` | Partial | No dedicated connector list. A connector is a word insertion, so light mode refuses it; hybrid mode catches it only when it pushes the novelty ratio past 12% |
| A7 | Block paraphrase expanding **more than 15%** of tokens | `docs/archive/Moteur DYS fr.md:18` | **Implemented** | `src/guardrails/policy.py`, wired into all three improvers via `should_accept_correction`, threshold 12% (decision I-1) |
| A8 | New-token ratio must stay **≤ 10–12%** ("stricter for DYS"); on failure return the normalized input | `docs/archive/Moteur DYS fr.md:33` | **Implemented** | `src/guardrails/policy.py`, threshold 12% (decision I-1). On failure light mode returns the input unchanged and hybrid mode returns light mode's correction (TODO-6); neither normalises |
| A9 | New-token ratio must stay **≤ 10–15%** (looser variant of A8) | `docs/archive/Conception French Version.md:69` | **Implemented** | `src/guardrails/policy.py`, wired into all three improvers via `should_accept_correction`, threshold 12% (decision I-1) |
| A10 | A single LT replacement must not grow a sentence by more than **1 token** | `docs/archive/Conception French Version.md:96` | **Implemented** | `_token_delta_ok`, `src/improvers/lt_improver.py:77`, applied at line 186 |
| A11 | Only replacements from a whitelist (articles, prepositions, contractions, punctuation) may be applied | `docs/archive/Conception French Version.md:97` | **Superseded** | The unreferenced whitelist was removed (TODO-2). Five per-replacement guards now do the job it was meant to, without blocking legitimate fixes like "sui"→"suis" |
| A12 | Verbs must never be swapped for synonyms; tense and lexeme preserved | `docs/Ideas prompt.txt:20` | Partial | Asked in the prompt, `src/improvers/llm_improver.py:99`. Since 2026-09-17 `validate_no_lost_content_words` (`src/guardrails/preservation.py`) refuses an output where a content word the user wrote no longer appears by spelling or sound, which catches a lexeme swap. A change of tense that leaves the verb recognisable still passes — "aller" -> "allé" is also what a correction looks like (TODO-14) |
| A13 | Register (familiar/formal) preserved; no summarizing, expanding or explaining | `docs/Ideas prompt.txt:39` | Partial | Asked in the prompt, `src/improvers/llm_improver.py:113`. Summarizing is caught since 2026-09-17 by `validate_no_lost_content_words`, and expanding by the novelty ratio; register itself is not checked (TODO-14) |

**Every rule in this section now has code behind it.** The validation layer that was five
`pass` stubs until 2026-09-08 is implemented and `should_accept_correction` is called by all
three improvers, so the LLM path is guarded too — it has no per-replacement filtering, so
this is the only thing between a rewrite and the user. Since 2026-09-17 it also refuses
outputs that drop or swap a word the user wrote (TODO-14), which moved A12 and A13 off
prompt-only.

Five remain partial, for two reasons: hybrid mode bounds new words with a ratio rather than
refusing each one (A1, A5, A6), and a rule about *how* to rewrite — tense, register — can
only be approximated after the fact (A12, A13).

---

## B. Anti-cheating policy

| # | Rule | Source | Status | Where |
|---|---|---|---|---|
| B1 | A deliberately incomplete prompt ("l'année de l'indépendance des États-Unis est le .. de ..") must come back **still incomplete** — the tool must not answer it | `docs/archive/Conception French Version.md:98`, `.tex:58,178` | Partial | Light mode blocks `DOUBLE_PUNCTUATION` (`_BLOCK_RULES`, TODO-10) and the QA corpus checks it on every run (`src/qa/runner.py`). Still no instruction in the shipped prompts; in hybrid mode a filled-in date or number is refused by the final gate, a filled-in word is not. "de" after the blank is capitalised (TODO-16) |
| B2 | Entity markers `ENT_X_Y` must be copied verbatim — never deleted, moved or altered | `docs/Ideas prompt.txt:15` | Prompt-only | `src/improvers/llm_improver.py:77`; reinjection at `src/guardrails/entities.py:128` restores originals but cannot detect a mangled marker |

B1 is a client acceptance criterion (`.tex:178`) and is the rule most exposed to a model
that decides to be helpful. In hybrid mode only the final gate stands in the way, and it
refuses a filled-in number or date but not a filled-in word.

---

## C. Allowed edit scope

| # | Rule | Source | Status | Where |
|---|---|---|---|---|
| C1 | Allowed: orthography, accents, elisions, French punctuation and thin spaces before `; : ? !` | `docs/archive/Moteur DYS fr.md:9`, `README.md:10` | Partial | Delegated wholesale to LanguageTool. The `src/normalize/fr_normalize.py` promised at `docs/archive/Conception French Version.md:37` does not exist |
| C2 | Soft segmentation: split an over-long sentence into **at most 2**, triggered at **30–35 words** | `docs/archive/Moteur DYS fr.md:12` | Not implemented | — |
| C3 | Minimal S-V-O reordering when LT proposes it | `docs/archive/Moteur DYS fr.md:14`, `README.md:10` | Not implemented | Contradicted by the shipped prompt, which forbids reordering. See I-2 |
| C4 | Frequent homophones (et/est, a/à, ou/où, ce/se, on/ont, son/sont, ces/ses, la/là) swappable only if the grammatical role is unchanged | `docs/archive/Moteur DYS fr.md:25` | Not implemented | — |
| C5 | Typical letter inversions (oi↔io, eu↔ue) allowed if Hunspell/LT validates | `docs/archive/Moteur DYS fr.md:26` | Not implemented | Hunspell is not a dependency of this project. See I-4 |
| C6 | Duplications and missing accents must always be corrected | `docs/archive/Moteur DYS fr.md:27` | Partial | Delegated to LT; no dedicated rule |
| C7 | Neologisms and low-frequency terms blocked via a high-frequency FR whitelist | `docs/archive/Moteur DYS fr.md:21` | **Implemented differently** | `validate_no_neologisms` uses spaCy's `is_oov` rather than a frequency lexicon; it separates invented forms from real vocabulary, which is what the rule targets |
| C8 | Only "safe" LT categories may be applied; unsafe categories blocked | `docs/archive/Conception French Version.md:92` | **Implemented differently** | Blocked by rule id (`_BLOCK_RULES`) rather than category: category granularity was too coarse. The inert empty sets were removed (TODO-3) |
| C9 | On guardrail failure, return the **normalized input** | `docs/archive/Conception French Version.md:69`, `docs/archive/Moteur DYS fr.md:34` | Partial | Light mode returns the input unchanged. Hybrid mode, since 2026-09-17, returns light mode's correction, per decision I-6 (TODO-6): `_fallback` in `src/improvers/llm_improver.py` and `ollama_improver.py`. Neither normalizes |
| C10 | Three-level intervention slider — **Fidèle** / **Équilibré** (default) / **Plus simple** (caps sentences at **25–28 words**) | `docs/archive/Moteur DYS fr.md:36-41` | Not implemented | No slider anywhere in `src/ui/`. The sidebar selects the engine, not an intervention level |
| C11 | Optional user dictionary (TXT of allowed surnames, toponyms, school jargon) loaded from `resources/` | `docs/archive/Moteur DYS fr.md:46` | Not implemented | — |

**Six of eleven have no implementation**, among them the intervention levels (C10) and
sentence splitting (C2), which is what readability (H6) is waiting for. C8, which used to be
present and inert, was replaced by blocking harmful rules by id.

---

## D. Hybrid pipeline and degradation

| # | Rule | Source | Status | Where |
|---|---|---|---|---|
| D1 | Fixed pipeline: mask entities → LT pre-pass → LLM rewrite → LT post-validation → reinject entities | `docs/archive/Conception French Version.md:73-80` | **Implemented** | `src/improvers/llm_improver.py:168-300`, `src/improvers/ollama_improver.py:57-103` |
| D2 | If the LT error score increases after the LLM pass, degrade back to the **LanguageTool output** | `docs/archive/Conception French Version.md:78`, `.tex:92` | **Implemented** | Since 2026-09-17 both improvers degrade to light mode's correction, not the input, on an error increase, a model error or a guardrail refusal (TODO-6). The hybrid pre-pass only collects hints, so the fallback runs the light improver in full. The comparison counts raw matches since TODO-1 |
| D3 | Default to Mistral-7B Q4 when RAM allows, otherwise Gemma3-4B; switch automatically on failure or OOM with no user action | `docs/archive/Conception French Version.md:82`, `.tex:88` | Not implemented | No hardware detection and no fallback. `src/services/factory.py:50` only lists what is installed; the user picks in `src/ui/layout.py:36`; on failure `app.py:35` shows an error and calls `st.stop()`. The `src/utils/hw.py` promised at `docs/archive/Conception French Version.md:44` does not exist |
| D4 | LLM hints limited to the **top 5** LanguageTool errors | `docs/archive/MistralTasks.md:133` | Partial | `src/improvers/llm_improver.py:126` uses `max(5, len(matches) * 0.1)`, exceeding 5 on long texts while the inline comment still says "Limit to top 5". `ollama_improver.py:47` does cap at 5 |
| D5 | Local journal (toggle) showing how many LT suggestions the guardrails rejected | `docs/archive/Moteur DYS fr.md:48` | Partial | stdout only, opt-in with the `LT_DEBUG_FILTER` env var, `src/improvers/lt_improver.py:28`. It defaulted to on until 2026-09-17 and wrote the user's text into the log file (TODO-12). No UI toggle |

---

## E. Accessibility

The reason the product exists.

| # | Rule | Source | Status | Where |
|---|---|---|---|---|
| E1 | Dyslexia-friendly fonts: Lexend, Atkinson Hyperlegible, OpenDyslexic | `README.md:8` | Not implemented | No occurrence of any of the three names anywhere in the repository. `src/ui/layout.py:74` hardcodes `font-family: sans-serif` |
| E2 | Adjustable font size | `README.md:8`, `.tex:59` | **Implemented** | `src/ui/appearance.py`, persisted to `%LOCALAPPDATA%\DYS-fr\config.yaml`. Overrides the root font size, which scales the whole interface because Streamlit sizes everything in `rem` |
| E3 | Adjustable line spacing | `README.md:8`, `.tex:59` | **Implemented** | `src/ui/appearance.py`, persisted to `%LOCALAPPDATA%\DYS-fr\config.yaml`. Default 1.6, which satisfies WCAG 1.4.12 |
| E4 | High-contrast mode | `README.md:8`, `.tex:59` | Not implemented | No `.streamlit/config.toml`, no theme toggle. Diff colours are hardcoded light-mode pastels, `src/ui/layout.py:82-91` |
| E5 | Distraction-free focus mode | `README.md:8` | **Implemented** | `src/ui/appearance.py`, persisted to `%LOCALAPPDATA%\DYS-fr\config.yaml`. Hides the Streamlit chrome and the sidebar, and ships its own exit button: hiding the sidebar with `display:none` leaves Streamlit believing it is expanded, so no native control appears |
| E6 | Diff view: additions underlined, deletions struck through | `docs/archive/Conception French Version.md:84`, `README.md:23`, `.tex:73` | **Implemented** | `src/ui/layout.py`. Additions are underlined rather than bold, and the `opacity: 0.8` that lowered contrast on deleted text is gone |
| E7 | Explicit "offline / no data sent" label in the UI | `docs/archive/Conception French Version.md:116` | **Implemented** | `src/ui/content.py:25` |
| E8 | Single-screen UI: text area, one action button, mode selector, diff and final text | `docs/archive/Conception French Version.md:107-113`, `.tex:103` | **Implemented** | `app.py:41-61`, `src/ui/layout.py:19-113` (an expander rather than tabs) |
| E9 | Loading progress bar and quality/latency profiles (Rapide / Équilibré / Max Qualité) | `docs/archive/Conception French Version.md:112` | Not implemented | Only a spinner, `app.py:29` |
| E10 | All user-facing strings in French, in one place | — | Partial | `src/ui/content.py` holds most, but French strings are hardcoded at `app.py:25,29,36,56` and `src/ui/layout.py:97-112` |

**Two of the five accessibility features the README advertises do not exist yet**:
dyslexia-friendly fonts (E1) and high contrast (E4). Font size, line spacing and focus mode
landed in phase 3a (E2, E3, E5), along with the diff view (E6). Quality/latency profiles
(E9) are not built.

---

## F. Offline and privacy guarantees

The strongest section: these hold.

| # | Rule | Source | Status | Where |
|---|---|---|---|---|
| F1 | Everything works **100% offline**; zero network calls at correction time | `.tex:45,55,96`, `README.md:14` | **Implemented** | LT on `127.0.0.1:8081` (`config.yaml:12`), spaCy local, llama.cpp in-process, Ollama on localhost. Verified as a release check, `docs/windows_release_checklist.md:56` |
| F2 | No account, no sign-up | `.tex:97` | **Implemented** | No authentication code exists |
| F3 | No external dependency (no system Java, no Internet) beyond first-run asset download | `docs/archive/Conception French Version.md:231` | **Implemented** | Embedded JRE. The installer channel needs no first-run download at all; see `docs/windows_distribution.md` |
| F4 | Downloads never live in the correction path | — | **Implemented** | No network call in `src/improvers/` or `src/guardrails/`; downloads isolated to `scripts/` and the packaging bootstrap |

---

## G. Performance and resources

| # | Rule | Source | Status | Where |
|---|---|---|---|---|
| G1 | A 1–2 sentence text corrected in **under 1 second** in light mode | `docs/archive/Conception French Version.md:172`, `.tex:177` | Not implemented | No timing assertion in `tests/` |
| G2 | Short paragraph in hybrid mode in **under 5–8 seconds** | `docs/archive/porposals.md:161` | Not implemented | — |
| G3 | Mistral-7B Q4_K_M needs **~5.5–6 GB** RAM at `n_ctx=4096`; reduce `n_ctx` when RAM is tight | `docs/archive/MistralTasks.md:376`, `docs/tools/Mistral.md:123` | Not enforced | `n_ctx` is configurable (`config.yaml:26`) but nothing checks available RAM. `use_mlock=True` is hardcoded at `src/improvers/llm_improver.py:59`, which `docs/archive/porposals.md:249` flags as harmful on low-RAM machines |
| G4 | Minimum **6 GB** free RAM and **~5 GB** free disk | `docs/tools/Mistral.md:8` | Not enforced | — |
| G5 | LLM generation bounded: `max_tokens` capped, temperature low for determinism | `config.yaml:27-28` | Partial | `max_tokens` is honoured. **`temperature` is not**: `config.yaml` sets `0.3`, `src/improvers/llm_improver.py:231` hardcodes `0.1` and never reads `self.temperature`, assigned at line 51. See TODO-4 |
| G6 | Ollama call must have an explicit timeout of **120 s** | `config.yaml:32` | Not implemented | `src/improvers/ollama_improver.py:78` passes only `temperature`; `timeout`, `num_predict` and `num_ctx` are never sent. See TODO-5 |
| G7 | LanguageTool server heap bounded to **256 MB** | `config.yaml:17` | **Implemented** | Consumed by `src/improvers/lt_server.py` and `src/runtime/languagetool.py` |
| G8 | `n_threads` should track physical cores, not `os.cpu_count()` | `docs/archive/porposals.md:220` | Not applied | `src/improvers/llm_improver.py:57` |
| G9 | Correction workloads need `n_ctx` **1024–2048**, not 4096 | `docs/archive/porposals.md:174` | Not applied | `config.yaml:26` is `4096` |
| G10 | MVP effort budget **50–71 h** | `docs/archive/Conception French Version.md:220` | N/A | Project management |

---

## H. QA acceptance criteria

| # | Rule | Source | Status | Where |
|---|---|---|---|---|
| H1 | QA corpus of **25–40** short anonymized DYS texts | `docs/archive/QA fr.md:5` | **Implemented differently** | `src/qa/corpus.py`: 30 hand-written texts with dyslexic errors injected per a published taxonomy (decision I-10). Simulated, not real DYS writing: no such corpus is downloadable (see `docs/completion-plan.md`) |
| H2 | E2E set of **20–30** typical French DYS sentences | `docs/archive/Conception French Version.md:165` | **Superseded** | By H1, decision I-10: texts rather than isolated sentences |
| H3 | Illegal additions (entities, dates, numbers) must be exactly **0%** | `docs/archive/QA fr.md:9` | Partial | Computed by `src/qa/metrics.py` and gated at exactly 0 by `tests/test_qa_acceptance.py`; holds at 0 on the fixed corpus and on seeds 7 and 42. Light mode only: the QA runner does not exercise hybrid mode |
| H4 | Spelling and grammar errors must drop by **≥ 80%** (LT pre/post count) | `docs/archive/QA fr.md:10`, `README.md:12` | Partial | Computed and gated at 80% by `tests/test_qa_acceptance.py`: 87.1% on the fixed corpus, light mode. Fails on another seed (78.6%, TODO-20), and hybrid mode is not measured |
| H5 | Mean sentence length **≤ 30–35 words** in Équilibré, **≤ 28** in Plus simple | `docs/archive/QA fr.md:11` | Partial | Computed and gated by `tests/test_qa_acceptance.py`: 7.5 words against the 35 bound. The 28-word "Plus simple" bound cannot apply until C10 exists |
| H6 | A French readability proxy must improve | `docs/archive/QA fr.md:12` | Not met | Computed by `src/qa/metrics.py` (syllables per sentence): 11.1 before, 11.2 after. Light mode never shortens a sentence, so this cannot improve until sentence splitting (C2) lands |
| H7 | Validation with **6–8 DYS users**, mean **≥ 4/5** on "clearer?" and "less tiring?" | `docs/archive/QA fr.md:13-15` | N/A | Human study; no records in the repository |
| H8 | Adversarial: input with no numbers/dates/entities → output identical | `docs/archive/QA fr.md:19` | **Implemented** | Adversarial corpus text checked on every QA run, `src/qa/runner.py` (`_check_adversarial`). Light mode |
| H9 | Adversarial: proper nouns never invented or modified | `docs/archive/QA fr.md:20` | **Implemented** | Adversarial corpus text checked on every QA run, `src/qa/runner.py`; plus `tests/test_languagetool.py:76` and `tests/test_llm_mistral.py:134` |
| H10 | Adversarial: **4–6 word** sentences must not be lengthened with connectors | `docs/archive/QA fr.md:21` | **Implemented** | Adversarial corpus text checked on every QA run, `src/qa/runner.py`. Light mode |
| H11 | Adversarial: mixed text (FR + acronyms/URLs) must not "correct" the URL or acronym | `docs/archive/QA fr.md:22` | **Implemented** | Adversarial corpus text checked on every QA run, `src/qa/runner.py`: "CAF", "SMS" and a URL must survive. Light mode |
| H12 | Hybrid QA: markers never altered; degradation on LT-score increase; simulated-OOM fallback to Gemma | `docs/archive/Conception French Version.md:171` | Partial | Degradation is fixed (TODO-1, TODO-6) and its wiring tested in `tests/test_hybrid_fallback.py`. Marker integrity is covered only indirectly: a mangled marker fails the final gate. The simulated-OOM fallback to Gemma does not exist (D3) |
| H13 | Unit tests for normalization, the LT suggestion parser, and the guardrail filters | `docs/archive/Conception French Version.md:164` | **Implemented** | `tests/test_lt_guardrails.py` (every per-replacement guard, normalisation, suggestion choice), `tests/test_guardrails_policy.py` (every final-gate validator, against the real spaCy model), `tests/test_hybrid_fallback.py` |
| H14 | Client acceptance: **1-click** install and launch | `.tex:176` | **Implemented** | `packaging/windows/smoke_test.py`, per `docs/windows_release_checklist.md:44` |
| H15 | Client acceptance: numbers, dates and names identical; ".." and "…" left uncompleted | `.tex:178` | Partial | Numbers, dates and names are enforced by the final gate in all three engines; ".." is kept in light mode (B1). The word after the blank is capitalised (TODO-16) |
| H16 | Client acceptance: changes visible in a diff, operation fully offline | `.tex:180` | **Implemented** | `src/ui/layout.py:93`; offline verified at `docs/windows_release_checklist.md:56` |

**The four quantitative metrics (H3–H6) are computed on every QA run** and the adversarial
texts (H8–H11) are checked, all in light mode. Two caveats keep this section from being
done: H6 does not improve, and H4 holds on the fixed corpus but not on every seed (TODO-20).
Hybrid mode is not measured by the runner at all.

---

## I. Contradictions between sources

Where the archived documents disagree with each other. These need a decision before the
rules above can be called a specification; they are queued in [TODO.md](TODO.md).

| # | Subject | The disagreement |
|---|---|---|
| I-1 | Novelty threshold | Three numbers: **≤ 10–15%** (`Conception:69`), **≤ 10–12%** (`Moteur:33`), block above **15%** (`Moteur:18`). The stub default is `0.15` |
| I-2 | Reordering | `Moteur:14` and `README.md:10` permit minimal S-V-O reordering; `docs/Ideas prompt.txt:37` forbids it outright, and the shipped prompt follows the prohibition |
| I-3 | Sentence splitting | `Moteur:12` and `README.md:10` allow splitting long sentences; `Ideas prompt.txt:37` forbids reformulating, and the shipped prompt dropped the instruction entirely |
| I-4 | Hunspell | `README.md:2,10` states the engine is built on LanguageTool **and Hunspell**; `Conception:222` recommends omitting it; no Hunspell code or dependency exists |
| I-5 | Default hybrid model | `Conception:82` and `.tex:84` say Mistral with automatic Gemma fallback; `porposals.md:17` claims the sidebar defaults to Gemma. Both are wrong: `src/ui/layout.py:41` uses `index=0` and `src/services/factory.py:56` appends Mistral first |
| I-6 | Degradation target | `Conception:78` and `.tex:92` say revert to the **LT output**; the code reverted to the **masked input** until TODO-6 aligned it with the spec on 2026-09-17 |
| I-7 | `max_tokens` | `docs/tools/Mistral.md:97` says 512; `config.yaml:27` says 526 |
| I-8 | Temperature | `docs/tools/Mistral.md:98` and `config.yaml:28` say 0.3; the code hardcodes 0.1 |
| I-9 | RAM requirement | `MistralTasks.md` is titled "CPU with ≤4 GB RAM" but concludes 5.5–6 GB at line 376; `docs/tools/Mistral.md:8` demands at least 6 GB |
| I-10 | QA corpus size | `Conception:165` says 20–30 sentences; `QA fr.md:5` says 25–40 texts |
| I-11 | `n_ctx` | `docs/tools/Mistral.md:96` and `config.yaml:26` set 4096; `porposals.md:174` argues correction needs only 1024–2048 and that 4096 causes swapping |
| I-12 | Model source | `MistralTasks.md:15` points at `TheBloke/…`; `docs/tools/Mistral.md:48` points at `bartowski/…` (the build uses bartowski) |
| I-13 | GGUF filename casing | `MistralTasks.md:20` uses `mistral-7b-instruct-v0.3.Q4_K_M.gguf`; `config.yaml:25` uses `Mistral-7B-Instruct-v0.3-Q4_K_M.gguf` |
| I-14 | Promised module layout | `Conception:37-45` specifies `src/normalize/fr_normalize.py`, `src/guardrails/numbers_dates.py`, `src/utils/diff.py`, `src/utils/hw.py`. None exist; the real file is `numbers_date.py` (singular) and it is empty |
| I-15 | Guardrail status | `Moteur:29` calls the guardrails "already planned (to enable by default)"; `README.md:10,16` presents them as shipped. Neither is true |

---

## J. Where the product actually stands

Of **71 documented rules**:

- **32 are enforced** — 27 outright, 3 implemented differently from the letter of the spec
  (C7, C8, H1), and 2 superseded (A11, H2). The offline guarantees (F), the packaged Windows
  delivery, most of the no-additions layer (A), reading comfort (E2, E3, E5, E6),
  degradation (D1, D2), and the QA corpus with its adversarial checks (H).
- **18 are partial** — approximated, or holding in one engine path but not the other.
- **1 is prompt-only** — marker integrity (B2).
- **18 are not implemented, not applied or not met** — the rest of the accessibility layer
  (E1 fonts, E4 high contrast, E9 profiles), most of the edit scope (C2–C5, C10, C11),
  performance and resource settings (G), and readability (H6).
- **2 are not software rules.**

Counts as of 2026-09-17. Section A went from six unimplemented rules to none when the
guardrail layer landed on 2026-09-09, and three of the five advertised accessibility
features now exist. The jump since then is partly new work — lost words (TODO-14) and
hybrid degradation (TODO-6) — and partly bookkeeping: the QA rows still described the state
before phases 1 and 2, and were only brought up to date on 2026-09-17 (DOC-3). Nothing is
"dead code" or "disabled" any more: the two entries that were (A11, C8) were resolved by
removing the inert code and replacing it.

The original pattern was that **what got built was the delivery mechanism, and what got
skipped was the safety layer and the accessibility layer** — the two things that
distinguish this product from running text through LanguageTool directly. The safety layer
now exists. The accessibility layer is still the gap, and it is the one a dyslexic reader
would notice first.

The offline promise, the hardest engineering commitment in the project, is the one that
fully holds.

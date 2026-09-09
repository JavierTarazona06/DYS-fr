# Completion Plan

How DYS-fr gets from what it does today to what its documentation promises.

This sits alongside two existing documents and replaces neither.
[business-rules.md](business-rules.md) is the inventory — 71 rules, their sources and their
real implementation status. [TODO.md](TODO.md) is a queue of defects and open decisions that
empties as they are fixed. **This file is the plan**: phases, ordering, acceptance criteria,
and the reasoning behind the sequence.

## The gap

At the start of this work, of the 71 documented rules: 15 implemented, 17 partial, 6
prompt-only, 2 written but inert, **28 with no implementation at all**, 3 not software.

What had been skipped was not peripheral. The two missing layers were the accessibility
layer — five features the README advertises, none of which existed — and the safety layer:
`src/guardrails/policy.py` was five `pass` stubs, `novelty.py` and `numbers_date.py` were
empty files, and `should_accept_correction` had zero call sites. Those two layers are
precisely what distinguishes DYS-fr from running text through LanguageTool directly.

**As of 2026-09-09 the safety layer is built** (phase 2). The accessibility layer is not,
and it is now the largest remaining gap. Current counts live in
[business-rules.md](business-rules.md#j-where-the-product-actually-stands).

This is a development programme measured in months, not a punch list. One useful
consequence: under this scope the README's false claims are resolved by building, not by
deleting.

## Constraints discovered

These shape the work and are easy to get wrong if you don't know them up front.

**Streamlit theme options cannot be changed at runtime.** Streamlit 1.51 has a complete
theming system — `theme.font`, `[[theme.fontFaces]]`, `theme.baseFontSize`, colours — but
every option is registered `scriptable=False`, so `st.set_option("theme.font", ...)` raises
`StreamlitAPIException`. Theme config is a launch-time baseline only. Anything the user
toggles must be CSS injection.

**Nothing writes the user config.** `src/utils/config.py:36` reads and deep-merges
`%LOCALAPPDATA%\DYS-fr\config.yaml` over the bundled one, but no code writes that file.
`save_user_config` is new work, and `packaging/windows/smoke_test.py` fails the build if
anything writes inside the install directory, so there is no alternative location.

**One function blocks four accessibility features.** `_generate_html_diff`
(`src/ui/layout.py:63-95`) hardcodes font, size, line-height and colours in inline `style=`
attributes, which win the CSS cascade. Line 74 alone blocks E1, E2, E3 and E4
simultaneously. Parameterising it unblocks all four and closes E6 (additions should be
underlined, not bold-on-green) at no extra cost.

**Fonts cannot live in `resources/`** — it is gitignored. Streamlit serves static files from
`<dir of app.py>/static/`, which is `<repo>/static/` in development and `_internal/static/`
frozen: the same relative path, which keeps packaging simple.

**No downloadable corpus of French dyslexic writing exists.** Published research provides
validated error taxonomies (phonological, visuo-orthographic, morphological) over samples of
20-32 French-speaking children; ORTOLANG hosts a general corpus of ~1,250 school writings,
not dyslexia-specific. Real dyslexic corpora are held by researchers and must be requested.
The generator is therefore grounded in the published taxonomy, with the project's own
documented patterns as a labelled subset inside those categories.

---

## Phase 0 — Unblock

Nothing else starts until the ten decisions below are approved: three of them govern the
same filter chain and the code cannot be written without them.

- Approve the ten decisions in the next section.
- Mark unbuilt features in `README.md` as in development.
- Fix the EV/SmartScreen paragraph in
  [windows_distribution.md](windows_distribution.md) — see the appendix.
- Re-verify the section E line citations in [business-rules.md](business-rules.md); the
  file has drifted about five lines.

**Done when** the decisions are approved and the README makes no unmarked false claim.

**Status: done.** Decisions approved 2026-09-08; README marked; the EV/SmartScreen paragraph
corrected; section E line citations re-verified.

## Phase 1 — Measurement (H1-H6)

First, and this is deliberate: it is the only thing that makes the rest verifiable. H4 asks
for a demonstrated ≥80% reduction in errors. Without a corpus and metrics, the guardrails
in phase 2 would be built blind and nobody could say whether they work.

- **Corpus generator**: 30 short texts, errors injected per the published taxonomy with the
  project's own patterns labelled inside it. Each text keeps its clean version, so the
  corpus carries its own ground truth.
- **Metrics**: illegal additions = 0% (H3), error reduction ≥80% measured with LanguageTool
  pre/post (H4), mean sentence length (H5), a French readability proxy (H6).
- **Runner** that executes the corpus against the engine and emits a report comparable
  across runs.

**Done when** pytest produces the four metrics and fails if H3 is not 0% or H4 falls below
the agreed threshold. That first run is the baseline everything else is measured against.

**Status: done.** `src/qa/` holds the taxonomy, corpus, metrics and runner;
`tests/test_qa_acceptance.py` is the gate. Run it with
`python -m src.qa.runner --json build/qa/report.json` (needs LanguageTool running).

### Measurements

| Metric | Baseline | With the guards | Target |
|---|---|---|---|
| H3 illegal additions | 1 | **0** | 0 |
| H4 error reduction | 92.5% (93 → 7) | **84.9%** (93 → 14) | ≥80% |
| H5 mean sentence words | 7.5 | 7.5 | ≤35 |
| H6 syllables/sentence | 11.1 → 11.2 | 11.1 → 11.2 | must improve |

H3, H4 and H5 pass. H6 does not improve, which is expected rather than a defect: light
mode fixes spelling and never shortens a sentence, so readability cannot move until the
bounded sentence splitting from decision I-3 lands in phase 3.

**The H4 drop is the price of H3, and it is the right trade.** The three guards cost 7.6
points of error reduction between them, because genuine double-punctuation, spelling and
grammar fixes are refused alongside the harmful ones. H3 is an absolute requirement at 0%;
H4 is a floor at 80% and sits comfortably above it. Recovering those points is a matter of
making the guards more precise, not of loosening them — and the corpus now measures any
such attempt in both directions at once.

### What the baseline run found

Two genuine defects, **both in light mode with no LLM involved**, recorded as TODO-9 and
TODO-10 and fixed the same day:

- LanguageTool replaced the garbled "duoze" with the commune name **"Eauze"**, inventing a
  proper noun. Guarded by `_does_not_introduce_proper_noun`.
- Its `DOUBLE_PUNCTUATION` rule collapsed a deliberate "`..`" blank, breaking client
  acceptance criterion B1 verbatim. Guarded by `_BLOCK_RULES`.
- Its `SUJET_AUXILIAIRE` rule inserted the verb "est" into "Il fiat chaud", adding a word
  the user never wrote. Guarded by `_does_not_insert_words`, which distinguishes
  re-segmenting the user's letters ("unepomme" → "une pomme", a correction dyslexic
  writers need) from inserting a new one.

All three were found by the corpus rather than by review, which is the argument for having
built the measurement first. Between them they moved A4, A5 and A6 in the inventory from
unimplemented to partial — enforced in the LanguageTool path, still unguarded in the LLM
one, which is what phase 2 finishes.

## Phase 2 — Safety layer (A2-A9, A11, C7, C8)

TODO-1, TODO-2, TODO-3 and the two defects the baseline run surfaced (TODO-9, TODO-10)
belong here rather than at the end: they are defects *of this layer*. TODO-1 means hybrid
mode can today return text worse than the input without telling anyone, and TODO-9 and
TODO-10 are live no-additions violations in light mode.

**TODO-9 and TODO-10 are done** (2026-09-08): H3 now holds at 0 and every adversarial check
passes. What remains in this phase is the guardrail layer proper — the `policy.py` stubs,
the two empty modules, and TODO-1 to TODO-3.

- Implement `src/guardrails/policy.py` for real: `validate_no_new_entities`,
  `validate_no_new_numbers_dates`, `validate_no_new_propn`, `validate_novelty_ratio`, and
  `should_accept_correction` as the orchestrator.
- Fill `novelty.py` and `numbers_date.py`, both empty files.
- Wire `should_accept_correction` into all three improvers.
- **TODO-1**: compare raw LanguageTool counts, not the truncated hint list. The correct line
  already exists, commented out, at `src/improvers/llm_improver.py:202`.
- **TODO-2 / TODO-3**: settle the whitelist and the empty category sets, and delete the
  comment claiming protections that do not exist.
- High-frequency whitelist to block neologisms (C7).

**Done when** phase 1 reports H3 = 0% and every validator has a unit test.

**Status: done, 2026-09-09.**

| Metric | Before phase 2 | After | Target |
|---|---|---|---|
| H3 illegal additions | 0 | **0** | 0 |
| H4 error reduction | 84.9% | **82.8%** (93 → 16) | ≥80% |
| H5 mean sentence words | 7.5 | 7.5 | ≤35 |

`src/guardrails/policy.py` is implemented and called by all three improvers;
`novelty.py` and `numbers_date.py` are filled; TODO-1 and TODO-3 are closed, TODO-2 is
resolved by removal. 34 unit tests cover the validators against the real spaCy pipeline.

**The hard part was not writing the checks, it was stopping them rejecting the product's
own work.** A literal reading of "NER(out) ⊆ NER(in)" and of the novelty ratio refuses
every spelling fix: correcting "supermarchet" scores 50% novelty, and restoring the accent
on "Noel" reads as an invented entity. Both guards had to be taught that a correction is
not an invention, using bounded Damerau-Levenshtein distance — transposition counts as one
edit, because letter inversion is the signature dyslexic error.

**One wrong turn worth recording.** Widening that tolerance to recover H4 pushed it to
82.8% by letting through the very rewrites the guards existed to stop — "depui" became
"d'appui", "kompliqué" became "complice". The fix was not calibration but granularity:
`_stays_close_to_the_original` judges a replacement against *its own span*, where a rewrite
is structurally far from what it replaces and a spelling fix is not. The whole-text layer
cannot make that call, because "preske" → "presque" and "depui" → "d'appui" are both two
edits apart.

Residual: TODO-11, where LanguageTool emits two separate replacements whose combined result
is gibberish. Left open deliberately rather than tightening the budget further, which would
start refusing legitimate fixes.

## Phase 3 — Accessibility (E1-E5, C10)

Three independent deliveries, in this order, so that packaging risk arrives last.

**3a — Mechanism, font size, line spacing, focus mode (~13 h).** Pure CSS, no packaging
changes. A new `src/ui/appearance.py`; the settings panel goes in the gap in
`src/ui/layout.py` between lines 54 and 56, using the `st.sidebar.expander` pattern already
established at `src/ui/model_manager.py:76`; the CSS injection goes immediately after
`st.set_page_config` in `app.py`, so the error and boot screens are styled too — otherwise a
dyslexic user meets an unstyled waiting screen. Includes `save_user_config`, the new French
strings in `content.py`, and the `_generate_html_diff` parameterisation.

**Status: 3a done, 2026-09-09.** `src/ui/appearance.py` with the settings panel in the
sidebar, `save_user_config` in `src/utils/config.py` (the writer that never existed), and
`_generate_html_diff` parameterised — which also closed E6. 22 unit tests, and the
behaviour verified in the browser: the root font-size override scales the whole interface
because Streamlit sizes everything in `rem`, so a 24px setting gives a 36px heading and a
52.8px line box in the text area.

**Two things the browser caught that no unit test would have.**

The settings panel snapped shut on every rerun, including the one triggered by moving a
slider inside it. Streamlit re-applies an expander's `expanded` argument whenever the value
*changes* between runs, so a computed flag fights the user. It is now decided once per
session and held constant.

More seriously, **focus mode stranded the user**. The plan assumed Streamlit would keep its
own sidebar-reopen control visible; it does not. Hiding the sidebar with `display:none`
leaves Streamlit believing it is still expanded, so `stSidebarCollapsedControl` is never
rendered — verified in the DOM. With the settings panel inside the hidden sidebar there was
no route back at all short of editing the config by hand. Focus mode now ships its own exit
button. A stranding bug in the one feature meant to reduce cognitive load is worse than the
feature being absent.

**3b — Dyslexia fonts (~8 h).** Lexend, Atkinson Hyperlegible and OpenDyslexic, all
OFL-1.1, as latin-subset WOFF2 (~200 KB total) in `static/fonts/` with their `OFL.txt`.
Requires a new entry in `datas` at `packaging/windows/dys_fr.spec:50-53`,
`--server.enableStaticServing=true` in the launcher argv, and a full frozen-build round trip
to prove the URL resolves inside `_internal/`. Budget for that loop: there is no fast path.

**3c — High contrast (~8-12 h).** CSS only, anchored on the stable `data-testid` hooks with
`!important`. The most likely to overrun: Streamlit's frontend is CSS-in-JS, so there is no
stylesheet to override, and making it look intentional rather than half-themed is where the
hours go.

The three intervention levels (C10, Fidèle / Équilibré / Plus simple) also land here. They
are a flag in the filter chain, not a new model.

**Done when** all five features exist, the smoke test still passes its install-directory
immutability check, and the in-development markers come out of the README.

## Phase 4 — Hybrid robustness (D3, TODO-4 to TODO-8)

- Automatic Gemma fallback with hardware detection — `src/utils/hw.py` was specified and
  never written.
- **TODO-4**: honour the configured temperature instead of the hardcoded 0.1.
- **TODO-5**: pass the timeout to Ollama.
- **TODO-6**: degrade to the LanguageTool output, not the masked input.
- **TODO-7**: physical-core thread count, `n_ctx` per decision I-11, revisit `use_mlock`.
- **TODO-8**: fix the misleading hint-cap comment.

**Done when** `TODO.md` is empty and the phase 1 metrics have not regressed.

---

## Decisions taken

Ten contradictions between the archived documents, all **approved on 2026-09-08**. None could
be resolved by reading the code, because in most cases the code implements neither option.
The reasoning is kept because the implementation phases depend on it.

| # | Question | Recommendation | Why |
|---|---|---|---|
| I-1 | Novelty ratio threshold: 10-15%, 10-12%, or block above 15%? | **12%**, configurable | The document specifically about the DYS engine chose the stricter bound "un peu plus strict pour DYS". For this population a false rejection returning the input unchanged is far cheaper than an accepted hallucination |
| I-2 | Is minimal reordering allowed? | **No** | It is the highest-risk edit for a no-new-information guarantee, nothing implements it, and the shipped prompt already forbids it. Adopting the prohibition costs nothing and makes three documents agree |
| I-3 | Is sentence splitting allowed? | **Yes, bounded**: only when LT proposes it or the sentence exceeds the threshold, at most 2 parts, never inventing connectors | Unlike reordering this is genuinely valuable — sentence length is the most cited readability lever for dyslexic readers — and it is in the client deliverable. It becomes a real feature in phase 3 alongside C10 |
| I-4 | Is Hunspell part of this product? | **No** — remove it from the README | LanguageTool already spell-checks French, the design document itself recommended dropping it, and there is no code or dependency. Cheapest of the ten to close, and it removes a public false claim |
| I-6 | Degradation fallback target | **LanguageTool output**, per the spec and the client deliverable | Reverting to the masked input discards validated corrections and hands the user less than light mode would have produced |
| I-7 | `max_tokens`: 512 or 526? | **512** | 526 reads as a typo and nothing depends on the odd value |
| I-9 | Stated RAM requirement | **4 GB for light mode, 8 GB recommended for hybrid** | The measured figure is 5.5-6 GB for the model alone at `n_ctx=4096`; adding the Python runtime and Streamlit makes a 6 GB total optimistic. Ties directly to the `use_mlock` question in TODO-7 |
| I-10 | QA corpus size: 20-30 sentences or 25-40 texts? | **30 texts** | Texts, not isolated sentences: H5 measures mean sentence length, which needs multi-sentence samples |
| I-11 | `n_ctx`: 4096 or 1024-2048? | **2048**, measured before and after in phase 4 | The project's own analysis says correction needs no more, and 4096 causes swapping on the target machines |
| I-12 | GGUF source and filename casing | **bartowski, pinned to an immutable revision**; casing as in `config.yaml` | That is what the build already uses. Pinning a revision instead of `/resolve/main/` stops a re-upload from breaking every installed copy's checksum |

## Explicitly out of scope

**H7, validation with 6-8 dyslexic users scoring ≥4/5.** This is a study with human
participants, not engineering work. Including it would mean this plan could never be
declared finished by anyone writing code. It remains a real acceptance criterion in
[business-rules.md](business-rules.md) and a real obligation to the client — it just is not
part of this plan.

Obtaining a real dyslexic corpus by contacting researchers or ORTOLANG is worth doing and
is not ruled out, but it takes weeks with an uncertain answer and must not block phase 1.

---

## Appendix — Code signing, deferred

Not being done now. Written down because the validation has a lead time nobody controls, and
because the previous guidance in this repository was wrong.

**The correction.** `windows_distribution.md` states that only an EV certificate is trusted
on first use. That has been false since **March 2024**: Microsoft removed EV's distinct
SmartScreen status, and OV and EV now accrue reputation identically, through download
volume. EV retains stricter identity verification and kernel-mode driver signing, neither of
which applies here. The earlier advice recommended paying more for a benefit that no longer
exists.

**What is true today:**

- Since June 2023 the private key must live on FIPS 140-2 Level 2 hardware or a cloud HSM.
  Downloadable `.pfx` files are no longer issued, for OV or EV.
- Azure Artifact Signing (formerly Trusted Signing) costs about $10/month, but new customers
  are restricted to US and Canadian organisations with three or more years of verifiable
  history, and individual onboarding is paused.
- Certum cloud signing (~$108/year with a legal entity) is the realistic European route.
  Their ~$50 Open Source certificate forbids commercially distributed software and fixes the
  publisher line to "Open Source Developer".
- Since 27 February 2026 a code signing certificate is valid for at most 459 days, so
  multi-year purchases no longer work as they used to.
- The build hook already exists: `build.ps1 -SignCertThumbprint`.

**Blocked on two facts only the project owners have**: whether there is a legal entity
behind the release, and whether the delivery is commercial. Those two answers pick the route.

# Archive

These documents are **historical intent, not specification**. They describe what DYS-fr
was planned to be between October and November 2025. The product diverged from them
during the implementation work that followed, and they contradict each other on several
points (thresholds, whether reordering is allowed, which model is the default).

They are kept because they record *why* the product took the shape it did, and because
they are the source of the rules catalogued in [../business-rules.md](../business-rules.md).

**Do not treat anything in this folder as a current requirement.** For what the product
actually does today, read [../business-rules.md](../business-rules.md). For what is still
open, read [../TODO.md](../TODO.md).

| File | Language | Was |
|---|---|---|
| `Conception French Version.md` | French | Overall design: architecture, module layout, UI, QA plan, effort budget |
| `Moteur DYS fr.md` | French | Correction-engine rules: allowed edits, guardrails, intervention levels |
| `QA fr.md` | French | QA acceptance criteria and adversarial tests |
| `MistralTasks.md` | Spanish | Local-LLM implementation notes and prompt drafts |
| `porposals.md` | Spanish | Later analysis of runtime problems; partly stale (its claim about the default model is wrong) |

The client-facing deliverable, `../Conception French Version Client/`, is **not** archived:
it is the only record of what was promised to the client.

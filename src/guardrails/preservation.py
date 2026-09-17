"""Lost words: the meaning a correction removed.

The counterpart of `novelty.py`. The no-additions policy asks what a correction put in; this
asks what it took out. Both change what the text says, and a reader who trusts the output
cannot see either. Found as TODO-14: the hybrid mode turned "Je sui aller au magasin." into
"Je suis au magasin.", and every other guard passed it — the verb was gone, nothing was
added, and the shorter sentence even had fewer LanguageTool errors.

The difficulty is telling a word that vanished from a word that was corrected beyond
recognition. "koman" -> "comment" is four edits, and a dyslexic writer's spelling is often
that far from the word. Three things make the distinction workable:

- **Alignment.** The two texts are aligned word by word, and a word is only looked for in
  the stretch of output that replaced it. A word is judged against what stands in its
  place, not against the whole text, where short words would match by accident.
- **Sound as well as spelling.** A correction of phonetic writing sounds like what the user
  wrote. A deletion leaves nothing that does, and a substitution — "quartier" -> "monde" —
  leaves something that sounds like a different word.
- **Stems.** Fixing a conjugation rewrites the end of a verb and keeps its beginning:
  "finisse" -> "finissaient". The output's lemma covers the rest: "prandue" -> "pris".

Measured on 2026-09-17 against 109 light-mode corrections and 39 hybrid-mode outputs: no
light-mode correction refused, and 10 hybrid outputs refused, every one of which dropped or
swapped a word — five of them had passed every other guard. A shared stem is also the known
blind spot: a substitution that starts like the user's word ("quartier" -> "quartz") passes.

Only content words count, as in the novelty ratio. Articles and prepositions come and go in
legitimate corrections ("de le" -> "du").
"""

from __future__ import annotations

from difflib import SequenceMatcher

from src.guardrails.novelty import CONTENT_POS
from src.utils.text import edit_budget, normalise_for_comparison, sound_key, within_edit_distance

#: A correction may merge up to this many words into one, or split one into this many:
#: "unepomme" -> "une pomme", "jai" -> "j'ai".
_MAX_JOIN = 3


#: Shortest shared beginning that counts as the same stem. Below this, "al" (aller) would
#: share a stem with "allumer".
_MIN_STEM = 3


def _words(doc) -> list[dict]:
    words = []
    for token in doc:
        if token.is_punct or token.is_space:
            continue
        form = normalise_for_comparison(token.text)
        if not form:
            continue
        words.append({
            "text": token.text,
            "form": form,
            "sound": sound_key(token.text),
            # The lemma lets a conjugation fix match: the user's "prandue" and the output's
            # "pris" share nothing, but "pris" is "prendre", which starts as "prandue" sounds.
            "lemma_form": normalise_for_comparison(token.lemma_),
            "lemma_sound": sound_key(token.lemma_),
            # Stop words are excluded even when tagged as content: "va" or "même" carry
            # little meaning, and spaCy tags them inconsistently on misspelt input.
            "content": token.pos_ in CONTENT_POS and not token.is_stop,
        })
    return words


def _close(a: str, b: str) -> bool:
    """Within edit budget, judged on the *shorter* of the two strings.

    A budget taken from the longer one lets a short word absorb a neighbour: "sui"+"aller"
    sounds like "suial", two edits from "sui". That is how "Je sui aller" -> "Je suis" first
    slipped past this very check.
    """
    if not a or not b:
        return False
    return within_edit_distance(a, b, edit_budget(min(a, b, key=len)))


def _same_stem(a: str, b: str) -> bool:
    """True when one word begins the other, give or take its last letter.

    Inflection changes the end of a word and keeps its beginning. A correction of verb
    agreement or tense — "finisse" -> "finissaient", "prand" -> "prendre" — is too far for
    an edit budget and is still the user's word. A deletion or a synonym shares no stem.
    """
    shorter, longer = sorted((a, b), key=len)
    if len(shorter) < _MIN_STEM:
        return False
    shared = 0
    for x, y in zip(shorter, longer):
        if x != y:
            break
        shared += 1
    return shared >= max(_MIN_STEM, len(shorter) - 1)


def _joins(words: list[dict], key: str):
    """(start, end, joined) for every run of 2 to _MAX_JOIN consecutive words."""
    for size in range(2, _MAX_JOIN + 1):
        for start in range(len(words) - size + 1):
            yield start, start + size, "".join(word[key] for word in words[start:start + size])


def _recognised(block: list[dict], replacement: list[dict]) -> set[int]:
    """Indices of `block` words that survive, respelt, reinflected, merged or split."""
    found = set()
    for key in ("form", "sound"):
        targets = [word[key] for word in replacement]
        targets += [joined for _, _, joined in _joins(replacement, key)]
        stems = [word[key] for word in replacement] + [word[f"lemma_{key}"] for word in replacement]
        for index, word in enumerate(block):
            if any(_close(word[key], target) for target in targets):
                found.add(index)
            elif any(_same_stem(word[key], stem) for stem in stems if stem):
                found.add(index)
        singles = [word[key] for word in replacement]
        for start, end, joined in _joins(block, key):
            if any(_close(joined, target) for target in singles):
                found.update(range(start, end))
    return found


def lost_content_words(original_doc, corrected_doc) -> list[str]:
    """Content words the user wrote that the correction removed or replaced with another word.

    A word still counts as present when it appears anywhere in the output with the same
    letters, so a removed duplication ("la maison maison") or a moved word is not a loss.
    Reordering is not this check's concern.
    """
    original = _words(original_doc)
    corrected = _words(corrected_doc)
    anywhere = {word["form"] for word in corrected}

    matcher = SequenceMatcher(
        None, [w["form"] for w in original], [w["form"] for w in corrected], autojunk=False
    )
    lost: list[str] = []
    for operation, i1, i2, j1, j2 in matcher.get_opcodes():
        if operation in ("equal", "insert"):
            continue
        block = original[i1:i2]
        recognised = _recognised(block, corrected[j1:j2])
        lost.extend(
            word["text"]
            for index, word in enumerate(block)
            if word["content"] and index not in recognised and word["form"] not in anywhere
        )
    return lost

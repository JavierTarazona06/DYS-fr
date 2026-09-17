"""Word alignment between what the user wrote and what a correction returned.

Shared by the two guards that ask whether a correction changed the words, from opposite
sides: `preservation.py` (did a word the user wrote disappear?) and `novelty.py` (did a
word appear that the user never wrote?).

Both face the same difficulty. A dyslexic writer's spelling is often far from the word they
meant — "koman" for "comment" is four edits — so spelling distance alone mistakes a
correction for a different word. And comparing a word against the *whole* other text is too
lenient: almost any short word sounds like something somewhere. Three tools, applied only
within the stretch of text that replaced the word, make the distinction workable:

- **Alignment.** The texts are aligned word by word, and a word is judged against what
  stands in its place.
- **Sound as well as spelling**, through `sound_key`: a correction of phonetic writing sounds
  like what the user wrote.
- **Stems.** Fixing a conjugation rewrites the end of a verb and keeps its beginning:
  "finisse" -> "finissaient". The lemma covers the rest: "prandue" -> "pris".
"""

from __future__ import annotations

from difflib import SequenceMatcher

from src.utils.text import edit_budget, normalise_for_comparison, sound_key, within_edit_distance

#: A correction may merge up to this many words into one, or split one into this many:
#: "unepomme" -> "une pomme", "jai" -> "j'ai".
_MAX_JOIN = 3

#: Shortest shared beginning that counts as the same stem. Below this, "al" (aller) would
#: share a stem with "allumer".
_MIN_STEM = 3


def words(doc) -> list[dict]:
    """The words of a spaCy doc, with the keys the comparisons below need."""
    result = []
    for token in doc:
        if token.is_punct or token.is_space:
            continue
        form = normalise_for_comparison(token.text)
        if not form:
            continue
        result.append({
            "index": token.i,
            "text": token.text,
            "pos": token.pos_,
            "is_stop": token.is_stop,
            "form": form,
            "sound": sound_key(token.text),
            # The lemma lets a conjugation fix match: the user's "prandue" and the output's
            # "pris" share nothing, but "pris" is "prendre", which starts as "prandue" sounds.
            "lemma_form": normalise_for_comparison(token.lemma_),
            "lemma_sound": sound_key(token.lemma_),
        })
    return result


def blocks(original: list[dict], corrected: list[dict]):
    """difflib opcodes aligning the two word lists by normalised form."""
    matcher = SequenceMatcher(
        None, [w["form"] for w in original], [w["form"] for w in corrected], autojunk=False
    )
    return matcher.get_opcodes()


def _close(a: str, b: str) -> bool:
    """Within edit budget, judged on the *shorter* of the two strings.

    A budget taken from the longer one lets a short word absorb a neighbour: "sui"+"aller"
    sounds like "suial", two edits from "sui". That is how "Je sui aller" -> "Je suis" first
    slipped past the lost-words check.
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


def _joins(block: list[dict], key: str):
    """(start, end, joined) for every run of 2 to _MAX_JOIN consecutive words."""
    for size in range(2, _MAX_JOIN + 1):
        for start in range(len(block) - size + 1):
            yield start, start + size, "".join(word[key] for word in block[start:start + size])


def recognised(block: list[dict], counterpart: list[dict]) -> set[int]:
    """Indices of `block` words that `counterpart` respells, reinflects, merges or splits."""
    found = set()
    for key in ("form", "sound"):
        targets = [word[key] for word in counterpart]
        targets += [joined for _, _, joined in _joins(counterpart, key)]
        stems = [word[key] for word in counterpart] + [word[f"lemma_{key}"] for word in counterpart]
        for index, word in enumerate(block):
            if any(_close(word[key], target) for target in targets):
                found.add(index)
            elif any(_same_stem(word[key], stem) for stem in stems if stem):
                found.add(index)
        singles = [word[key] for word in counterpart]
        for start, end, joined in _joins(block, key):
            if any(_close(joined, target) for target in singles):
                found.update(range(start, end))
    return found


def corrections_of_user_words(original_doc, corrected_doc) -> set[int]:
    """Token indices in `corrected_doc` of words that stand in for a word the user wrote.

    Only words from a *replaced* stretch qualify. An inserted word has no counterpart and is
    never covered here, however much it sounds like something else in the text.
    """
    original, corrected = words(original_doc), words(corrected_doc)
    found: set[int] = set()
    for operation, i1, i2, j1, j2 in blocks(original, corrected):
        if operation != "replace":
            continue
        block = corrected[j1:j2]
        found.update(block[k]["index"] for k in recognised(block, original[i1:i2]))
    return found

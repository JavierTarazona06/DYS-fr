"""The QA corpus: 30 short French texts with dyslexic errors injected deterministically.

Each item carries its own ground truth — the clean text it was derived from and the list of
errors applied — so metrics can be computed without a separate answer key. Generation is
seeded, so two runs of the same seed produce byte-identical corpora and results stay
comparable across changes to the engine.

The texts are multi-sentence on purpose: H5 measures mean sentence length, which single
sentences cannot express. Several texts are adversarial rather than typical, and are tagged
so the runner can assert the specific rules they exist to test.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from src.qa.error_taxonomy import INJECTORS, ErrorCategory, InjectedError

DEFAULT_SEED = 20260908
DEFAULT_ERRORS_PER_TEXT = 4

#: Texts tagged with this are used verbatim: their point is that a correct input must
#: survive untouched, so injecting errors would defeat the test.
TAG_NO_INJECTION = "no_injection"

#: Adversarial tags, each tied to a rule in docs/business-rules.md.
TAG_NO_ENTITIES = "no_entities"          # H8  output must be identical
TAG_PROPER_NOUNS = "proper_nouns"        # H9  proper nouns never invented or modified
TAG_SHORT_SENTENCES = "short_sentences"  # H10 4-6 word sentences must not be lengthened
TAG_MIXED_ACRONYMS = "mixed_acronyms"    # H11 acronyms and URLs must not be "corrected"
TAG_INCOMPLETE = "incomplete"            # B1  a deliberate blank must not be filled in
TAG_NUMBERS_DATES = "numbers_dates"      # A3  numbers and dates must survive unchanged


@dataclass(frozen=True)
class BaseText:
    id: str
    text: str
    tags: tuple[str, ...] = ()


@dataclass(frozen=True)
class CorpusItem:
    id: str
    clean: str
    errored: str
    injected: tuple[InjectedError, ...] = field(default_factory=tuple)
    tags: tuple[str, ...] = ()

    @property
    def has_tag(self):
        return lambda tag: tag in self.tags


#: 30 short texts of everyday French. Written by hand rather than generated, because they
#: are the reference against which every metric is computed.
BASE_TEXTS: tuple[BaseText, ...] = (
    BaseText("t01", "Je suis allé au supermarché pour acheter du pain et du lait. "
                    "La caissière a fermé la caisse à dix-huit heures. "
                    "Je suis rentré chez moi sans rien."),
    BaseText("t02", "Hier, ma sœur a préparé une tarte aux pommes. "
                    "Elle a mis trop de sucre dans la pâte. "
                    "Nous l'avons mangée quand même."),
    BaseText("t03", "Le professeur nous a demandé de lire le chapitre trois. "
                    "Je n'ai pas compris la dernière question. "
                    "Je lui écrirai demain matin."),
    BaseText("t04", "Mon frère travaille dans une boulangerie depuis septembre. "
                    "Il se lève très tôt et rentre fatigué. "
                    "Le week-end, il dort beaucoup."),
    BaseText("t05", "Nous avons pris le train pour aller voir nos cousins. "
                    "Le voyage a duré presque quatre heures. "
                    "Il pleuvait quand nous sommes arrivés."),
    BaseText("t06", "La bibliothèque ferme à dix-neuf heures le vendredi. "
                    "J'ai emprunté deux livres sur les animaux marins. "
                    "Je dois les rendre avant la fin du mois."),
    BaseText("t07", "Ce matin, le bus était en retard à cause de la neige. "
                    "Beaucoup d'élèves sont arrivés après la sonnerie. "
                    "Le directeur n'a rien dit."),
    BaseText("t08", "Ma mère a acheté une nouvelle machine à laver. "
                    "L'ancienne faisait un bruit terrible. "
                    "Le livreur est venu jeudi après-midi."),
    BaseText("t09", "Je joue au football tous les mercredis avec mes amis. "
                    "Notre équipe a perdu le dernier match. "
                    "L'entraîneur nous a dit de continuer."),
    BaseText("t10", "Le médecin m'a expliqué qu'il fallait dormir davantage. "
                    "Je me couche souvent après minuit. "
                    "Je vais essayer de changer mes habitudes."),
    BaseText("t11", "Pendant les vacances, nous sommes allés à la montagne. "
                    "Il y avait encore de la neige au sommet. "
                    "Mon père a pris beaucoup de photos."),
    BaseText("t12", "La voisine garde son chien dans le jardin. "
                    "Il aboie dès que quelqu'un passe devant la grille. "
                    "Cela réveille tout le quartier."),
    BaseText("t13", "J'ai commencé un nouveau livre la semaine dernière. "
                    "L'histoire se passe dans un village au bord de la mer. "
                    "Je le trouve difficile mais intéressant."),
    BaseText("t14", "Le magasin de vêtements a changé de propriétaire. "
                    "Les prix ont augmenté depuis le mois de mars. "
                    "Ma tante préfère aller ailleurs maintenant."),
    BaseText("t15", "Nous avons repeint la cuisine en jaune clair. "
                    "Cela a pris tout le week-end. "
                    "Le résultat est vraiment joli."),
    BaseText("t16", "Mon ordinateur s'éteint tout seul depuis quelques jours. "
                    "Le réparateur pense que la batterie est usée. "
                    "Je dois attendre la pièce."),
    BaseText("t17", "La maîtresse a organisé une sortie au musée. "
                    "Nous partons le douze mai avec deux autres classes. "
                    "Il faut apporter un pique-nique."),
    BaseText("t18", "Je n'aime pas beaucoup écrire des rédactions. "
                    "Les mots se mélangent quand je vais trop vite. "
                    "Je préfère raconter les choses à voix haute."),
    BaseText("t19", "Le boulanger prépare les croissants avant cinq heures. "
                    "L'odeur remplit toute la rue. "
                    "Les clients attendent devant la porte."),
    BaseText("t20", "Ma grand-mère habite dans une petite maison à la campagne. "
                    "Elle cultive des tomates et des courgettes. "
                    "Nous lui rendons visite chaque été."),
    BaseText("t21", "Le train de sept heures quarante est souvent complet. "
                    "Je dois rester debout jusqu'à la troisième gare. "
                    "Ensuite, je trouve toujours une place."),
    BaseText("t22", "Nous avons adopté un chat au refuge de la ville. "
                    "Il était très craintif les premiers jours. "
                    "Maintenant il dort sur le canapé."),
    BaseText("t23", "Le cours de mathématiques commence à huit heures trente. "
                    "J'oublie souvent ma calculatrice à la maison. "
                    "Le professeur me prête la sienne."),
    BaseText("t24", "Mon oncle répare des vélos dans son garage. "
                    "Il m'a montré comment changer une chambre à air. "
                    "Ce n'est pas si compliqué."),

    # --- adversarial: correct input with no entities, must come back identical (H8) ---
    BaseText("t25", "Le ciel est gris depuis ce matin. "
                    "Le vent souffle fort dans les arbres. "
                    "Nous restons à la maison aujourd'hui.",
             (TAG_NO_ENTITIES, TAG_NO_INJECTION)),

    # --- adversarial: proper nouns must never be invented or altered (H9) ---
    BaseText("t26", "Camille et Jonathan habitent à Villeneuve-sur-Lot depuis 2019. "
                    "Leur fille Éléonore étudie à Bordeaux. "
                    "Ils se retrouvent à Noël chez Madame Grandchamp.",
             (TAG_PROPER_NOUNS, TAG_NUMBERS_DATES)),

    # --- adversarial: very short sentences must not be padded with connectors (H10) ---
    BaseText("t27", "Le chat dort. Il fait chaud. Je bois de l'eau. "
                    "Marie arrive bientôt. Nous partons après.",
             (TAG_SHORT_SENTENCES,)),

    # --- adversarial: acronyms and URLs must not be "corrected" (H11) ---
    BaseText("t28", "J'ai envoyé le dossier à la CAF avant la date limite. "
                    "Le formulaire se trouve sur https://www.service-public.fr/particuliers. "
                    "La réponse arrive par SMS ou par courrier.",
             (TAG_MIXED_ACRONYMS, TAG_NO_INJECTION)),

    # --- adversarial: a deliberate blank must come back still blank (B1) ---
    BaseText("t29", "Nous avons étudié la révolution en cours d'histoire. "
                    "L'année de l'indépendance des États-Unis est le .. de .. "
                    "Je dois retrouver la date avant lundi.",
             (TAG_INCOMPLETE, TAG_NO_INJECTION, TAG_PROPER_NOUNS)),

    # --- adversarial: dense numbers and dates, none of which may change (A3) ---
    BaseText("t30", "Le rendez-vous est fixé au 14 mars 2026 à 9 h 45. "
                    "Il faut apporter 2 photos et 35 euros en espèces. "
                    "Le bureau se trouve au 3e étage, porte 412.",
             (TAG_NUMBERS_DATES, TAG_NO_INJECTION)),
)


def _inject(text: str, rng: random.Random, count: int) -> tuple[str, list[InjectedError]]:
    """Apply up to `count` distinct injectors, skipping any that find no candidate."""
    order = list(INJECTORS)
    rng.shuffle(order)

    applied: list[InjectedError] = []
    current = text
    for injector in order:
        if len(applied) >= count:
            break
        candidate, error = injector.apply(current, rng)
        if error is not None:
            current = candidate
            applied.append(error)
    return current, applied


def generate_corpus(
    seed: int = DEFAULT_SEED,
    errors_per_text: int = DEFAULT_ERRORS_PER_TEXT,
) -> list[CorpusItem]:
    """Build the corpus. Deterministic for a given seed."""
    items: list[CorpusItem] = []
    for base in BASE_TEXTS:
        if TAG_NO_INJECTION in base.tags:
            items.append(CorpusItem(base.id, base.text, base.text, (), base.tags))
            continue

        # A per-text seed keeps one text's errors from shifting when another changes.
        rng = random.Random(f"{seed}:{base.id}")
        errored, applied = _inject(base.text, rng, errors_per_text)
        items.append(CorpusItem(base.id, base.text, errored, tuple(applied), base.tags))
    return items


def corpus_summary(items: list[CorpusItem]) -> dict:
    """Counts by category and by tag, for the report header."""
    by_category = {category.value: 0 for category in ErrorCategory}
    for item in items:
        for error in item.injected:
            by_category[error.category.value] += 1

    by_tag: dict[str, int] = {}
    for item in items:
        for tag in item.tags:
            by_tag[tag] = by_tag.get(tag, 0) + 1

    return {
        "texts": len(items),
        "injected_errors": sum(len(item.injected) for item in items),
        "by_category": by_category,
        "by_tag": by_tag,
    }

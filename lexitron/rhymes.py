"""Rhymes, Lexitron's rhyming dictionary: the ry command.

Pronunciations come from the CMU Pronouncing Dictionary, with words it lacks
derived from ones it has ("chasms" from "chasm") or guessed; see
scripts/build_pronunciations.py.
"""

import sys, os, re, gzip, argparse, shutil
from functools import lru_cache
from importlib import resources
from itertools import product
from typing import Callable, Dict, FrozenSet, Iterable, List, Optional, Set, Tuple

from .lexitron import (DIM, RESET, base_forms, formatted, letters_of,
                       load_words, parse_length, pattern_regex, search,
                       size_style, use_color, version, word_sizes)

PRONUNCIATIONS = 'pronunciations.tsv.gz'
# Rhymes are for writing, so by default they're words most people know
RHYME_LEVEL = 60
# How different near rhymes may sound at most (see near_cost): always up to
# NEAR_CLOSE, and further, up to NEAR_LIMIT, for words with fewer than
# NEAR_ENOUGH near rhymes that close
NEAR_LIMIT = 1.0
NEAR_CLOSE = 0.6
NEAR_ENOUGH = 30
OPEN_COST = 0.3
# The most pronunciations of a phrase to try, as each word may have several
MAX_VARIANTS = 8
SORT_ORDERS = ('syllables', 'common', 'alpha')
BOLD = '\033[1m'

# Phonemes are ARPAbet, as in the CMU Pronouncing Dictionary. Vowels carry a
# stress: 1 primary, 2 secondary, 0 none.
CONSONANTS = 'B CH D DH F G HH JH K L M N NG P R S SH T TH V W Y Z ZH'.split()
VOWELS = 'AA AE AH AO AW AY EH ER EY IH IY OW OY UH UW'.split()
PHONEMES = CONSONANTS + [v + s for v in VOWELS for s in '012']
# Pronunciations are stored and compared as strings with one character per
# phoneme, from "0" on
CODE = {p: chr(0x30 + i) for i, p in enumerate(PHONEMES)}
PHONEME = {c: p for p, c in CODE.items()}
# Each vowel's code mapped to the vowel without its stress
VOWEL_OF = {CODE[v + s]: v for v in VOWELS for s in '012'}
STRESSED = frozenset(CODE[v + s] for v in VOWELS for s in '12')
# Turns each vowel unstressed, to compare vowels whatever their stress
UNSTRESS = str.maketrans({CODE[v + s]: CODE[v + '0']
                          for v in VOWELS for s in '12'})
# Also turns the unstressed "ih" into "uh", which the CMU Pronouncing
# Dictionary uses for much the same sound ("orange" has both)
REDUCE = str.maketrans({**{CODE[v + s]: CODE[v + '0']
                           for v in VOWELS for s in '12'},
                        CODE['IH0']: CODE['AH0']})
AH2 = CODE['AH2']
# Turns primary stress into secondary, for the second part of a compound
DEMOTE = str.maketrans({CODE[v + '1']: CODE[v + '2'] for v in VOWELS})


def encode(arpabet: str) -> str:
    """Encode an ARPAbet pronunciation like "K AE1 T".

    Raises:
        KeyError: If a phoneme isn't ARPAbet, or a vowel has no stress
    """
    return ''.join(CODE[p] for p in arpabet.upper().split())


def decode(pron: str) -> str:
    """Decode a pronunciation into ARPAbet, like "K AE1 T"."""
    return ' '.join(PHONEME[c] for c in pron)


def is_arpabet(text: str) -> bool:
    """Whether text is an ARPAbet pronunciation with at least one stressed
    vowel, like "K AE1 T", rather than a word."""
    phonemes = text.split()
    return (bool(phonemes) and all(p in CODE for p in phonemes)
            and any(p[-1] in '12' for p in phonemes))


def rhyme_part(pron: str) -> str:
    """The part of a pronunciation that rhymes: from its last stressed vowel
    on ("cat" AE1 T, "democrat" AE2 T, "happy" AE1 P IY0), or from its last
    vowel if none is stressed."""
    last = len(pron) - 1
    for i in range(last, -1, -1):
        if pron[i] in STRESSED:
            # The CMU Pronouncing Dictionary gives some unstressed "uh"s
            # secondary stress ("additionally", "gaga"); count only one in a
            # closed last syllable, as in "backup"
            if pron[i] == AH2 and (i == last or any(
                    c in VOWEL_OF for c in pron[i + 1:])):
                continue
            return pron[i:]
    for i in range(last, -1, -1):
        if pron[i] in VOWEL_OF:
            return pron[i:]
    return pron


def rhyme_key(pron: str) -> str:
    """What two pronunciations share if they rhyme: their rhyme parts,
    whatever the stress, with unstressed "ih" and "uh" the same."""
    part = rhyme_part(pron)
    return part[0].translate(UNSTRESS) + part[1:].translate(REDUCE)


def is_stressed(pron: str) -> bool:
    """Whether a pronunciation has a stressed vowel; words that don't, like
    "the" and "to", are too weak to rhyme."""
    return any(c in STRESSED for c in pron)


def syllables(pron: str) -> int:
    return sum(c in VOWEL_OF for c in pron)


# Words the CMU Pronouncing Dictionary lacks, pronounced from ones it has

SIBILANTS = frozenset(encode('S Z SH ZH CH JH'))
VOICELESS = frozenset(encode('P T K F TH S SH CH HH'))
IY0 = CODE['IY0']


def add_s(pron: str) -> str:
    """A plural or -s form: "cat" + S, "dog" + Z, "horse" + IH0 Z."""
    if pron[-1] in SIBILANTS:
        return pron + encode('IH0 Z')
    return pron + (CODE['S'] if pron[-1] in VOICELESS else CODE['Z'])


def add_ed(pron: str) -> str:
    """A past form: "walk" + T, "rain" + D, "want" + IH0 D."""
    if pron[-1] in (CODE['T'], CODE['D']):
        return pron + encode('IH0 D')
    return pron + (CODE['T'] if pron[-1] in VOICELESS else CODE['D'])


def adding(arpabet: str) -> Callable[[str], str]:
    ending = encode(arpabet)
    return lambda pron: pron + ending


def y_to(arpabet: str) -> Callable[[str], Optional[str]]:
    """A suffix replacing a final -y, as in "happily": IY0 -> AH0 L IY0."""
    ending = encode(arpabet)
    return lambda pron: pron[:-1] + ending if pron.endswith(IY0) else None


def stems(stem: str) -> Iterable[str]:
    """The words a stem left by -ed, -ing, -er or -est may have come from:
    "hopp" (hopped) from "hop", "hop" (hoped) from "hope", "rain" (rained)
    from "rain"."""
    if len(stem) > 2 and stem[-1] == stem[-2] and stem[-1] not in 'aeiou':
        return (stem, stem[:-1])
    if stem and stem[-1] not in 'aeiouy':
        return (stem + 'e', stem)
    return (stem, stem + 'e')


def same(stem: str) -> Iterable[str]:
    return (stem,)


def plus_y(stem: str) -> Iterable[str]:
    return (stem + 'y',)


def sibilant(stem: str) -> Iterable[str]:
    return (stem,) if stem.endswith(('s', 'x', 'z', 'ch', 'sh', 'o')) else ()


# (suffix, the words it may have been added to, the pronunciation it makes),
# longest suffixes first
SUFFIXES = [
    ('iness', plus_y, adding('N AH0 S')),
    ('ness', same, adding('N AH0 S')),
    ('ment', same, adding('M AH0 N T')),
    ('ship', same, adding('SH IH2 P')),
    ('hood', same, adding('HH UH2 D')),
    ('less', same, adding('L AH0 S')),
    ('like', same, adding('L AY2 K')),
    ('wise', same, adding('W AY2 Z')),
    ('able', stems, adding('AH0 B AH0 L')),
    ('ably', stems, adding('AH0 B L IY0')),
    ('iest', plus_y, adding('AH0 S T')),
    ('ful', same, adding('F AH0 L')),
    ('ism', stems, adding('IH2 Z AH0 M')),
    ('ist', stems, adding('IH0 S T')),
    ('ish', stems, adding('IH0 SH')),
    ('dom', same, adding('D AH0 M')),
    ('ily', plus_y, y_to('AH0 L IY0')),
    ('ies', plus_y, add_s),
    ('ied', plus_y, add_ed),
    ('ier', plus_y, adding('ER0')),
    ('est', stems, adding('AH0 S T')),
    ('ing', stems, adding('IH0 NG')),
    ("'s", same, add_s),
    ('es', sibilant, adding('IH0 Z')),
    ('ed', stems, add_ed),
    ('er', stems, adding('ER0')),
    ('ly', same, adding('L IY0')),
    ("s'", same, lambda pron: pron),
    ('s', same, add_s),
]

# (prefix, its pronunciation); the stress stays on the word it's added to
PREFIXES = [(prefix, encode(arpabet)) for prefix, arpabet in [
    ('counter', 'K AW2 N T ER0'), ('under', 'AH2 N D ER0'),
    ('inter', 'IH2 N T ER0'), ('super', 'S UW2 P ER0'),
    ('multi', 'M AH2 L T IY0'), ('over', 'OW2 V ER0'),
    ('anti', 'AE2 N T IY0'), ('semi', 'S EH2 M IY0'),
    ('self', 'S EH2 L F'), ('non', 'N AA2 N'), ('dis', 'D IH0 S'),
    ('mis', 'M IH0 S'), ('pre', 'P R IY0'), ('out', 'AW2 T'),
    ('micro', 'M AY2 K R OW0'), ('hyper', 'HH AY2 P ER0'),
    ('ultra', 'AH2 L T R AH0'), ('mega', 'M EH2 G AH0'),
    ('mini', 'M IH2 N IY0'), ('post', 'P OW2 S T'), ('bio', 'B AY2 OW0'),
    ('sub', 'S AH2 B'), ('un', 'AH0 N'), ('re', 'R IY0'), ('co', 'K OW2'),
    ('be', 'B IH0'),
]]
# Two-letter words that end compounds, as in "mashup"
PARTICLES = {'up', 'on', 'in', 'by'}

# British spellings and their American equivalents, which the CMU
# Pronouncing Dictionary is more likely to have
SPELLINGS = [
    (re.compile(r'(?<=[a-z]{2})our(?=s?$|ed|ing|er|ite|able|less|ful)'), 'or'),
    (re.compile(r'(?<=[a-z]{2})is(?=(e|ed|es|er|ers|ing|ation|ations|able)$)'), 'iz'),
    (re.compile(r'ys(?=(e|ed|es|ing)$)'), 'yz'),
    (re.compile(r'(?<=[bcdfgkmnpstvz])re(?=s?$|d$)'), 'er'),
    (re.compile(r'ogue(?=s?$)'), 'og'),
    (re.compile(r'(?<=[a-z])ae'), 'e'),
    (re.compile(r'(?<=[a-z])oe(?=[a-z])'), 'e'),
    (re.compile(r'ence(?=s?$)'), 'ense'),
    (re.compile(r'mme(?=s?$)'), 'm'),
    (re.compile(r'plough'), 'plow'),
]


def derive(word: str, lookup: Callable[[str], Optional[Tuple[str, ...]]],
           is_word: Callable[[str], bool],
           is_common: Optional[Callable[[str], bool]] = None,
           depth: int = 3) -> Tuple[str, ...]:
    """Pronounce a word from the pronunciations of words it's made from.

    Tries, in order: a suffix ("chasms" as "chasm" + Z), a prefix
    ("unbuilding"), an American spelling ("humanise" as "humanize"), and
    two words ("sheepherder" as "sheep" + "herder"). Each part may itself
    be derived.

    Args:
        lookup: The known pronunciations of a word, if any
        is_word: Whether a spelling is a real word, so "hoped" isn't taken
            for "hop" + T
        is_common: Whether a word is common enough to be a three-letter
            part of a compound ("cat" in "catwalk"); by default, is_word
        depth: How many steps of derivation to allow

    Returns:
        The word's pronunciations, or () if it can't be derived
    """
    is_common = is_common or is_word

    def pronounce(part, steps):
        return lookup(part) or (derive(part, lookup, is_word, is_common, steps)
                                if steps else ())

    if depth <= 0:
        return ()
    for suffix, sources, make in SUFFIXES:
        if not word.endswith(suffix) or len(word) - len(suffix) < 2:
            continue
        stem = word[:-len(suffix)]
        for base in sources(stem):
            if not is_word(base):
                continue
            made = [m for m in map(make, pronounce(base, depth - 1)) if m]
            if made:
                return tuple(dict.fromkeys(made))
    for prefix, sound in PREFIXES:
        rest = word[len(prefix):]
        if word.startswith(prefix) and len(rest) >= 3 and is_word(rest):
            found = pronounce(rest, depth - 1)
            if found:
                return tuple(sound + pron for pron in found)
    for spelling, replacement in SPELLINGS:
        american = spelling.sub(replacement, word)
        if american != word:
            found = pronounce(american, depth - 1)
            if found:
                return found
    # Two words, the second unstressed relative to the first, splitting
    # where both parts are longest. Short parts are often not words at all
    # here ("sec" in "secant"), so they have to be common, or a particle at
    # the end ("mashup").
    def is_part(part):
        return is_word(part) and (len(part) > 3 or is_common(part))

    splits = sorted(range(3, len(word) - 1),
                    key=lambda i: -min(i, len(word) - i))
    for i in splits:
        first, second = word[:i], word[i:]
        if is_part(first) and (second in PARTICLES or
                               len(second) >= 3 and is_part(second)):
            heads, tails = lookup(first), pronounce(second, depth - 1)
            if heads and tails:
                return tuple(head + tail.translate(DEMOTE)
                             for head, tail in product(heads[:2], tails[:2]))
    return ()


# The bundled pronunciations

@lru_cache(maxsize=None)
def load_pronunciations() -> Tuple[Dict[str, Tuple[str, ...]], FrozenSet[str]]:
    """Load the bundled pronunciations.

    Returns:
        A dictionary from each lowercase word to its pronunciations, and the
        words whose pronunciations are guesses
    """
    with resources.files('lexitron').joinpath(PRONUNCIATIONS).open('rb') as f:
        text = gzip.decompress(f.read()).decode('ascii')
    prons, guessed = {}, set()
    for line in text.split('\n'):
        if not line or line.startswith('#'):
            continue
        word, source, codes = line.split('\t')
        prons[word] = tuple(codes.split(' '))
        if source == 'g':
            guessed.add(word)
    return prons, frozenset(guessed)


@lru_cache(maxsize=None)
def known_words() -> FrozenSet[str]:
    """Every word in the word list, lowercased."""
    return frozenset(word.lower() for word, _, _, _ in load_words())


def tokens(text: str) -> List[str]:
    """The words of a phrase, lowercased: "sperm whale" -> sperm, whale."""
    return [t for t in re.split(r"[\s-]+", text.lower()) if t]


def pronunciations(text: str,
                   lookup: Optional[Callable[[str], Tuple[str, ...]]] = None
                   ) -> Tuple[str, ...]:
    """The pronunciations of a word or phrase, or () if a word in it is
    unknown.

    Args:
        lookup: The pronunciations of one word; by default, the bundled ones
    """
    if lookup is None:
        lookup = load_pronunciations()[0].get
    parts = []
    for token in tokens(text):
        found = lookup(token)
        if not found:
            return ()
        parts.append(found)
    combined = (''.join(p) for p in product(*parts))
    return tuple(dict.fromkeys(p for p, _ in zip(combined, range(MAX_VARIANTS))))


def sounds_like(word: str) -> Optional[str]:
    """The known word whose spelling ends most like word's, sharing at
    least its last three letters, to guess how it's pronounced; the most
    common one if there are several."""
    prons = load_pronunciations()[0]
    sizes = word_sizes()
    for k in range(len(word) - 1, 2, -1):
        ending = word[-k:]
        found = [w for w in prons if w.endswith(ending) and w != word]
        if found:
            return min(found, key=lambda w: (sizes.get(w, 100), len(w), w))
    return None


def pronounce_query(text: str) -> Tuple[Tuple[str, ...], List[str]]:
    """Pronounce what the user asked to rhyme: a word, a phrase, or ARPAbet.

    Returns:
        The pronunciations, and notes on any that were guessed
    """
    if is_arpabet(text):
        return (encode(text),), []
    prons, guessed = load_pronunciations()
    notes = []

    def lookup(token):
        if token in prons:
            if token in guessed:
                notes.append(f"the pronunciation of '{token}' is a guess")
            return prons[token]
        found = derive(token, prons.get, known_words().__contains__)
        if found:
            return found
        like = sounds_like(token)
        if like:
            notes.append(f"guessing '{token}' sounds like '{like}'")
            return prons[like]
        return ()

    return pronunciations(text, lookup), notes


# Near rhymes

# (place, manner, voiced) for each consonant
FEATURES = {
    'P': ('lips', 'stop', 0), 'B': ('lips', 'stop', 1),
    'T': ('ridge', 'stop', 0), 'D': ('ridge', 'stop', 1),
    'K': ('velum', 'stop', 0), 'G': ('velum', 'stop', 1),
    'F': ('teeth', 'fricative', 0), 'V': ('teeth', 'fricative', 1),
    'TH': ('dental', 'fricative', 0), 'DH': ('dental', 'fricative', 1),
    'S': ('ridge', 'fricative', 0), 'Z': ('ridge', 'fricative', 1),
    'SH': ('palate', 'fricative', 0), 'ZH': ('palate', 'fricative', 1),
    'HH': ('throat', 'fricative', 0),
    'CH': ('palate', 'affricate', 0), 'JH': ('palate', 'affricate', 1),
    'M': ('lips', 'nasal', 1), 'N': ('ridge', 'nasal', 1),
    'NG': ('velum', 'nasal', 1),
    'L': ('ridge', 'liquid', 1), 'R': ('palate', 'liquid', 1),
    'W': ('lips', 'glide', 1), 'Y': ('palate', 'glide', 1),
}

# Pairs of vowels that sound alike
NEAR_VOWELS = {frozenset(pair.split()) for pair in [
    'IY IH', 'IH EH', 'EH AE', 'AE AA', 'AA AO', 'AA AH', 'AO OW', 'OW UW',
    'UH UW', 'UH AH', 'AH ER', 'EY EH', 'EY IY', 'AY AA', 'AW AA', 'OY AO',
    'IH AH', 'AH EH',
]}
# Unstressed vowels that are all much the same "uh"
REDUCED = {'AH', 'IH'}


def consonant_cost(a: str, b: str) -> float:
    """How different two consonants sound, from 0 (the same) to 1."""
    if a == b:
        return 0.0
    place_a, manner_a, voiced_a = FEATURES[a]
    place_b, manner_b, voiced_b = FEATURES[b]
    voicing = 0.25 if voiced_a != voiced_b else 0.0
    if manner_a == manner_b:
        if place_a == place_b:
            return voicing
        return (0.35 if manner_a == 'nasal' else 0.5) + voicing
    if {manner_a, manner_b} == {'fricative', 'affricate'} and place_a == place_b:
        return 0.35 + voicing
    if {manner_a, manner_b} <= {'liquid', 'glide'}:
        return 0.5
    if place_a == place_b:
        return min(0.6 + voicing, 0.9)
    return 0.9


def indel_cost(c: str) -> float:
    """How much adding or dropping a consonant changes the sound; least for
    the ones endings add, like "cat" -> "cats" or "cast"."""
    return 0.35 if c in ('S', 'Z', 'T', 'D') else 0.3 if c == 'HH' else 0.5


@lru_cache(maxsize=None)
def cluster_cost(a: Tuple[str, ...], b: Tuple[str, ...]) -> float:
    """How different two runs of consonants sound: an edit distance."""
    row = [0.0]
    for c in b:
        row.append(row[-1] + indel_cost(c))
    for x in a:
        previous, row = row, [row[0] + indel_cost(x)]
        for j, y in enumerate(b):
            row.append(min(previous[j] + consonant_cost(x, y),
                           previous[j + 1] + indel_cost(x),
                           row[j] + indel_cost(y)))
    return row[-1]


def vowel_cost(a: str, b: str, stressed: bool) -> float:
    if a == b:
        return 0.0
    if not stressed and {a, b} <= REDUCED:
        return 0.1
    return 0.5 if frozenset((a, b)) in NEAR_VOWELS else 1.0


@lru_cache(maxsize=None)
def split_rhyme(part: str) -> Tuple[Tuple[str, ...], Tuple[Tuple[str, ...], ...]]:
    """Split a rhyme part into its vowels and the consonants after each:
    AE1 S T -> (AE,), ((S, T),)."""
    vowels, clusters = [], []
    for c in part:
        if c in VOWEL_OF:
            vowels.append(VOWEL_OF[c])
            clusters.append([])
        elif clusters:
            clusters[-1].append(PHONEME[c])
    return tuple(vowels), tuple(tuple(c) for c in clusters)


@lru_cache(maxsize=None)
def near_cost(a: str, b: str, assonance: bool = False) -> Optional[float]:
    """How different two rhyme parts sound, or None if they don't rhyme at
    all: 0 for a perfect rhyme, up to NEAR_LIMIT for a near rhyme.

    They need the same number of syllables. The stressed vowel counts
    double, and must be the same or close.

    Args:
        assonance: The vowels must be the same, and only the consonants
            count, with no limit
    """
    (vowels_a, clusters_a), (vowels_b, clusters_b) = split_rhyme(a), split_rhyme(b)
    if len(vowels_a) != len(vowels_b):
        return None
    if assonance:
        if vowels_a != vowels_b:
            return None
        return sum(cluster_cost(x, y) for x, y in zip(clusters_a, clusters_b))
    cost = 2 * vowel_cost(vowels_a[0], vowels_b[0], True)
    if cost >= 2:
        return None
    cost += sum(vowel_cost(x, y, False)
                for x, y in zip(vowels_a[1:], vowels_b[1:]))
    if cost > NEAR_LIMIT:
        return None
    cost += sum(cluster_cost(x, y) for x, y in zip(clusters_a, clusters_b))
    if bool(clusters_a[-1]) != bool(clusters_b[-1]):
        # Ending on a vowel or not makes more difference than one consonant
        # more: "love" is nearer "rough" than "duh"
        cost += OPEN_COST
    return cost if cost <= NEAR_LIMIT else None


# Finding rhymes

def rhymes(prons: Iterable[str], words: Iterable[str], kind: str = 'perfect',
           exclude: Iterable[str] = ()) -> List[Tuple[str, int, float]]:
    """Find the words that rhyme with any of the pronunciations.

    Args:
        prons: Pronunciations to rhyme with
        words: Words to choose from (as from lexitron.search)
        kind: 'perfect' (the same sounds from the last stressed vowel on),
            'near' (similar sounds; see near_cost) or 'assonance' (the same
            vowels, any consonants). Near rhymes and assonance leave out
            perfect rhymes.
        exclude: Words to leave out, compared by their letters (the word
            being rhymed)

    Returns:
        (word, syllables, cost) for each rhyme, cost being 0 for a perfect
        rhyme and higher the less alike it sounds. Words pronounced exactly
        like one of prons (homophones) are left out.
    """
    prons = tuple(prons)
    parts = {rhyme_part(p) for p in prons}
    keys = {rhyme_key(p) for p in prons}
    unstressed = {p.translate(UNSTRESS) for p in prons}
    skip = {letters_of(w) for w in exclude}
    found = []
    for word in words:
        if letters_of(word) in skip:
            continue
        best = None
        for pron in pronunciations(word):
            if not is_stressed(pron):
                continue
            if pron.translate(UNSTRESS) in unstressed:
                # A homophone: rhyming it would just repeat the word
                best = None
                break
            key = rhyme_key(pron)
            if kind == 'perfect':
                cost = 0.0 if key in keys else None
            elif key in keys:
                # Perfect rhymes are listed on their own
                best = None
                break
            else:
                part = rhyme_part(pron)
                costs = [c for c in (near_cost(target, part, kind == 'assonance')
                                     for target in parts) if c is not None]
                cost = min(costs) if costs else None
            if cost is not None and (best is None or cost < best[1]):
                best = (syllables(pron), cost)
        if best:
            found.append((word, best[0], best[1]))
    return found


def closest(found: List[Tuple[str, int, float]]) -> List[Tuple[str, int, float]]:
    """Keep the near rhymes up to NEAR_CLOSE, or if there are fewer than
    NEAR_ENOUGH of those, the closest NEAR_ENOUGH (and any as close as the
    last of them)."""
    costs = sorted(round(cost, 2) for _, _, cost in found)
    limit = NEAR_CLOSE
    if len(costs) >= NEAR_ENOUGH:
        limit = max(limit, costs[NEAR_ENOUGH - 1])
    elif costs:
        limit = costs[-1]
    return [m for m in found if round(m[2], 2) <= limit]


def weak_rhymes(words: Iterable[str], prons: Iterable[str], word: str,
                inflections: bool = False) -> Set[str]:
    """The rhymes that add little: words made by putting a word in front of
    word ("bobcat" for "cat"), and with inflections, inflections of word or
    of its perfect rhymes ("cats" and "bats" as near rhymes for "cat")."""
    keys = {rhyme_key(p) for p in prons}
    forms = base_forms()
    known = known_words()
    word = word.lower()

    def is_compound(w):
        w = w.lower()
        front = w[:-len(word)].rstrip(" -'")
        return (w.endswith(word) and bool(front)
                and all(t in known for t in tokens(front)))

    def rhymes_or_is(base):
        return letters_of(base) == letters_of(word) or any(
            rhyme_key(p) in keys for p in pronunciations(base))

    return {w for w in words if is_compound(w) or inflections
            and any(map(rhymes_or_is, forms.get(w, ())))}


def ordered(found: List[Tuple[str, int, float]], sort: str,
            sizes: Dict[str, int], last: Set[str] = frozenset()
            ) -> List[Tuple[str, int, float]]:
    """Sort rhymes: by syllables, then how alike they sound, then how
    common the word is ('syllables'); by how common ('common'); or
    alphabetically ('alpha').

    Args:
        last: Words to put after the others (but for 'alpha'), as from
            weak_rhymes
    """
    commonness = lambda m: sizes.get(m[0], 100)
    key = {
        'syllables': lambda m: (m[1], m[0] in last, round(m[2], 2),
                                commonness(m), m[0].lower()),
        'common': lambda m: (m[0] in last, commonness(m), round(m[2], 2),
                             m[0].lower()),
        'alpha': lambda m: (m[0].lower(), m[0]),
    }[sort]
    return sorted(found, key=key)


# The command line

DESCRIPTION = """\
Find rhymes for a word or phrase: perfect rhymes by default, grouped by
syllables, most common first. A rhyme matches the sounds from the last
stressed vowel on, so "cat" rhymes with "acrobat". Weak rhymes (bobcat)
come last. An expression, as in lx, narrows the results: ry cat 'b.*'"""

EPILOG = """\
examples:
  ry orange                    near rhymes, as it has no perfect ones
  ry -N love                   near rhymes: rough, stuff, enough, ...
  ry -y 2 -L 50 money          everyday two-syllable rhymes
  ry 'make it rain'            rhymes for a phrase
  ry "K AE1 T"                 rhymes for a pronunciation (ARPAbet)

More: <https://github.com/rothos/lexitron>"""


def make_parser() -> argparse.ArgumentParser:
    """Build the command line argument parser."""
    usage = "ry [options] word [expression]"
    parser = argparse.ArgumentParser(prog='ry', usage=usage,
        description=DESCRIPTION, epilog=EPILOG, add_help=False,
        formatter_class=lambda prog: argparse.RawDescriptionHelpFormatter(
            prog, max_help_position=27))
    parser.add_argument('terms', nargs='*', help=argparse.SUPPRESS)

    # Which rhymes
    kinds = parser.add_mutually_exclusive_group()
    kinds.add_argument('-N', '--near',
        dest='near', action='store_true',
        help='near rhymes: sounds alike, closest first')
    kinds.add_argument('-A', '--assonance',
        dest='assonance', action='store_true',
        help='same vowel sounds, any consonants')
    parser.add_argument('-y', '--syllables', metavar='N',
        dest='syllables',
        help='number of syllables: 2, 1-3, 3- or -2')

    # Filters, as in lx
    parser.add_argument('-s', '--substring',
        dest='substring', action='store_true',
        help='the expression matches anywhere in the word')
    parser.add_argument('-l', '--length', metavar='N',
        dest='length',
        help='number of letters: 5, 4-7, 5- or -7')
    parser.add_argument('-i', '--include', metavar='LETTERS',
        dest='include',
        help='must contain these letters')
    parser.add_argument('-e', '--exclude', metavar='LETTERS',
        dest='exclude',
        help='must not contain these letters')
    parser.add_argument('-t', '--pattern', metavar='PATTERN',
        dest='pattern',
        help='shape, as in lx: abba matches deed')

    # Which words to search
    parser.add_argument('-L', '--level', metavar='N',
        dest='level', type=int, default=RHYME_LEVEL,
        help=f'obscurity, 35 to 95: default {RHYME_LEVEL}')
    parser.add_argument('-b', '--base-only',
        dest='base_only', action='store_true',
        help='leave out plurals, conjugations, etc')
    phrases = parser.add_mutually_exclusive_group()
    phrases.add_argument('-p', '--phrases',
        dest='phrases', action='store_true',
        help='include phrases, like "sperm whale"')
    phrases.add_argument('-P', '--phrases-only',
        dest='only_phrases', action='store_true',
        help='only phrases')
    proper = parser.add_mutually_exclusive_group()
    proper.add_argument('-u', '--uppercase',
        dest='include_proper', action='store_true',
        help='include proper words, like "Paris"')
    proper.add_argument('-U', '--uppercase-only',
        dest='only_proper', action='store_true',
        help='only proper words')

    # Output
    parser.add_argument('-o', '--sort', metavar='ORDER',
        dest='sort', choices=SORT_ORDERS, default='syllables',
        help='syllables (default), common or alpha')
    parser.add_argument('-n', '--number-only',
        dest='number', action='store_true',
        help='print only the number of rhymes')
    parser.add_argument('-I', '--info',
        dest='show_info', action='store_true',
        help='print a header with the pronunciation')
    parser.add_argument('-x', '--plain',
        dest='unformatted', action='store_true',
        help='one word per line, no columns or color')
    parser.add_argument('-h', '--help',
        action='help',
        help='show this help')
    parser.add_argument('-v', '--version',
        action='version', version="Lexitron " + version(),
        help='show the version')
    return parser


def print_rhymes(sections: List[Tuple[str, List[Tuple[str, int, float]]]],
                 args: argparse.Namespace, header: str, notes: List[str]):
    """Print rhymes.

    Args:
        sections: (heading, rhymes) for each way of saying the word that
            rhymes differently ("read" as reed or red); the heading is
            shown only if there's more than one
        header: Describes the search, for -I
        notes: Things to mention, like a guessed pronunciation
    """
    words = list(dict.fromkeys(w for _, found in sections for w, _, _ in found))
    if args.unformatted or not sys.stdout.isatty():
        # Notes and the header go to stderr, so stdout stays machine-readable
        for note in notes:
            print(f"({note})", file=sys.stderr)
        if args.show_info:
            print(header, file=sys.stderr)
        if args.number:
            print(len(words))
        elif words:
            print('\n'.join(words))
        return

    color = use_color()
    dim = (lambda s: DIM + s + RESET) if color else (lambda s: s)
    bold = (lambda s: BOLD + s + RESET) if color else (lambda s: s)
    for note in notes:
        print(dim(f"({note})"))
    if args.number:
        print(header if args.show_info else len(words))
        return
    if args.show_info:
        print(header)
    width, height = shutil.get_terminal_size()
    width = width - 1  # Wiggle room
    sizes = word_sizes(args.level, args.base_only)
    lines = []
    for heading, found in sections:
        if len(sections) > 1:
            lines += ['', bold(heading)] if lines or args.show_info else [bold(heading)]
        if not found:
            lines.append(dim('none'))
            continue
        groups = [('', found)]
        if args.sort == 'syllables':
            counts = sorted({n for _, n, _ in found})
            groups = [(f"{n} syllable{'s' if n != 1 else ''}",
                       [m for m in found if m[1] == n]) for n in counts]
        for title, group in groups:
            names = [w for w, _, _ in group]
            styles = None
            if color:
                styles = {w: DIM if w in args.weak else size_style(sizes[w])
                          for w in names if w in sizes}
            if title:
                if lines or args.show_info:
                    lines.append('')
                lines.append(dim(title))
            # Fill the width: rhymes are read across, a few per group
            lines.append(formatted(names, width, 2, styles))
    print('\n'.join(lines))


def main(argv: List[str] = None):
    """Entry point for the ry command."""
    parser = make_parser()
    args = parser.parse_intermixed_args(sys.argv[1:] if argv is None else argv)

    if not 1 <= len(args.terms) <= 2:
        parser.error("give a word (or phrase, in quotes) to rhyme, "
                     "optionally followed by an expression")
    query = args.terms[0]
    expression = args.terms[1] if len(args.terms) == 2 else None

    ranges = {}
    for name in ('length', 'syllables'):
        spec = getattr(args, name)
        if spec:
            try:
                ranges[name] = parse_length(spec)
            except ValueError as e:
                parser.error(str(e).replace('length', name))
    if args.pattern:
        try:
            pattern_regex(args.pattern)
        except ValueError as e:
            parser.error(str(e))

    prons, notes = pronounce_query(query)
    if not prons:
        parser.error(f"can't tell how to pronounce {query!r}; give its "
                     "pronunciation in ARPAbet instead, like \"K AE1 T\"")

    try:
        found = search(
            '.*' if expression is None else expression,
            substring=args.substring,
            base_only=args.base_only,
            common=not args.only_proper,
            proper=args.include_proper or args.only_proper,
            level=args.level,
            phrases=args.phrases or args.only_phrases,
            single_words=not args.only_phrases,
            length=ranges.get('length'),
            include=args.include,
            exclude=args.exclude,
            pattern=args.pattern,
            sort='alpha')
    except re.error as e:
        parser.error(f"invalid regular expression: {e}")
    candidates = found['proper'] + found['common']

    kind = 'near' if args.near else 'assonance' if args.assonance else 'perfect'
    low, high = ranges.get('syllables', (0, float('inf')))
    # One section for each way of saying the word that rhymes differently
    by_key = {}
    for pron in prons:
        by_key.setdefault(rhyme_key(pron), []).append(pron)

    def find(kind):
        sections = []
        for group in by_key.values():
            matches = [m for m in rhymes(group, candidates, kind, [query])
                       if low <= m[1] <= high]
            if kind == 'near':
                matches = closest(matches)
            heading = f"{query} ({' or '.join(decode(p) for p in group)})"
            sections.append((heading, matches))
        return sections

    def weak(sections):
        return weak_rhymes([w for _, found in sections for w, _, _ in found],
                           prons, query, inflections=kind != 'perfect')

    sections = find(kind)
    if kind == 'perfect':
        everything = [w for _, found in sections for w, _, _ in found]
        weaklings = weak(sections)
        if not set(everything) - weaklings:
            only = f" but {', '.join(sorted(weaklings))}" if weaklings else ''
            notes.append(f"no perfect rhymes for '{query}'{only}; "
                         "showing near rhymes")
            kind = 'near'
            sections = find(kind)

    # Weak rhymes go last, dimmed
    args.weak = weak(sections)
    sizes = word_sizes(95, args.base_only)
    sections = [(heading, ordered(found, args.sort, sizes, args.weak))
                for heading, found in sections]

    total = len({w for _, found in sections for w, _, _ in found})
    noun = {'perfect': 'rhyme', 'near': 'near rhyme',
            'assonance': 'assonant word'}[kind]
    header = (f"{total} {noun}{'' if total == 1 else 's'} for '{query}' "
              f"({' or '.join(decode(p) for p in prons)})")

    try:
        print_rhymes(sections, args, header, notes)
        sys.stdout.flush()
    except BrokenPipeError:
        # The reader went away (e.g. `ry ... | head`); exit quietly.
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        sys.exit(1)

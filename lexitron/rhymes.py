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
# With fewer perfect rhymes than this, show near rhymes after them
FEW = 10
# Long rhymes whose consonants differ at most this much come first
LONG_CLOSE = 1.0
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
PRIMARY = frozenset(CODE[v + '1'] for v in VOWELS)
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


def counts_as_stressed(pron: str, i: int) -> bool:
    """Whether the vowel at i is stressed, for rhyming. The CMU Pronouncing
    Dictionary gives some unstressed "uh"s secondary stress ("additionally",
    "gaga"); only one in a closed last syllable counts, as in "backup"."""
    if pron[i] not in STRESSED:
        return False
    return pron[i] != AH2 or (i < len(pron) - 1 and not any(
        c in VOWEL_OF for c in pron[i + 1:]))


def rhyme_part(pron: str) -> str:
    """The part of a pronunciation that rhymes: from its last stressed vowel
    on ("cat" AE1 T, "democrat" AE2 T, "happy" AE1 P IY0), or from its last
    vowel if none is stressed."""
    for i in range(len(pron) - 1, -1, -1):
        if counts_as_stressed(pron, i):
            return pron[i:]
    for i in range(len(pron) - 1, -1, -1):
        if pron[i] in VOWEL_OF:
            return pron[i:]
    return pron


def last_syllables(pron: str, n: int) -> Optional[int]:
    """Where the last n syllables of a pronunciation start, at their first
    vowel, or None if it has fewer."""
    seen = 0
    for i in range(len(pron) - 1, -1, -1):
        if pron[i] in VOWEL_OF:
            seen += 1
            if seen == n:
                return i
    return None


def rhyme_tail(pron: str, n: int, long: bool = False) -> Optional[str]:
    """The last n syllables of a pronunciation, from their first vowel on,
    if that vowel is stressed, to compare with a rhyme part of n syllables.
    It may be longer than the word's own rhyme part: "curfew" K ER1 F Y UW2
    has ER1 F Y UW2, to rhyme with "hurt you".

    Args:
        long: To compare with a long part (see long_part), where any
            stressed vowel counts
    """
    i = last_syllables(pron, n)
    if i is None or not (pron[i] in STRESSED if long
                         else counts_as_stressed(pron, i)):
        return None
    if not long and pron[i] not in PRIMARY and any(c in PRIMARY
                                                   for c in pron[i + 1:]):
        # A stronger stress later has another rhythm: "hitherto" HH IH1 DH
        # ER2 T UW1 doesn't rhyme with "hurt you"
        return None
    return pron[i:]


def long_part(pron: str) -> Optional[str]:
    """The part of a pronunciation from the stressed vowel before its rhyme
    part on, for long rhymes ("education" EH2 JH AH0 K EY1 SH AH0 N), or
    None if it has none. A secondary-stressed "uh" counts here, as in
    "understand"."""
    start = len(pron) - len(rhyme_part(pron))
    stressed = [i for i in range(start) if pron[i] in STRESSED]
    return pron[stressed[-1]:] if stressed else None


# T or D and the Y of a following "you" run together: "hurt you" sounds like
# "virtue", "miss you" like "tissue"
COALESCE = [(encode(a), encode(b)) for a, b in
            [('T Y', 'CH'), ('D Y', 'JH'), ('S Y', 'SH'), ('Z Y', 'ZH')]]


def coalesced(part: str) -> str:
    for joined, sound in COALESCE:
        part = part.replace(joined, sound)
    return part


def key_of(part: str) -> str:
    """What two rhyme parts share if they rhyme: their sounds, whatever the
    stress, with unstressed "ih" and "uh" the same."""
    part = coalesced(part)
    return part[0].translate(UNSTRESS) + part[1:].translate(REDUCE)


def rhyme_key(pron: str) -> str:
    """What two pronunciations share if they rhyme (see key_of)."""
    return key_of(rhyme_part(pron))


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


# Words that go unstressed in a phrase. Not ones that are often stressed,
# like "up" and "out" ("turn it up").
FUNCTION_WORDS = frozenset("""
    a an the i me my you your he him his she her it its we us our they them
    their of to at by for from with as and or but nor if than that
    is am are was were be been do does did has have had can could will would
    shall should may might must
""".split())
# The ones that follow a verb, as in "hurt you"
OBJECTS = frozenset('me you him her it us them'.split())


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
    words, parts = tokens(text), []
    for token in words:
        found = lookup(token)
        if not found:
            return ()
        parts.append(found)
    # In a phrase, little words like "you" and "the" go unstressed, so "hurt
    # you" rhymes with "virtue"; unless they're all there is ("of you")
    weak = [i for i, token in enumerate(words) if token in FUNCTION_WORDS]
    if len(weak) == len(words):
        weak = weak[:-1]
    for i in weak:
        parts[i] = tuple(dict.fromkeys(p.translate(UNSTRESS) for p in parts[i]))
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
    all: 0 for a perfect rhyme, up to NEAR_LIMIT for a near rhyme. Each may
    be said with T Y run together as CH, or not (see COALESCE).

    They need the same number of syllables. The stressed vowel counts
    double, and must be the same or close.

    Args:
        assonance: The vowels must be the same, and only the consonants
            count, with no limit
    """
    costs = [c for c in (separate_cost(x, y, assonance)
                         for x in {a, coalesced(a)} for y in {b, coalesced(b)})
             if c is not None]
    return min(costs) if costs else None


def separate_cost(a: str, b: str, assonance: bool) -> Optional[float]:
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
           exclude: Iterable[str] = (), wrenched: bool = False
           ) -> List[Tuple[str, int, float]]:
    """Find the words that rhyme with any of the pronunciations.

    Args:
        prons: Pronunciations to rhyme with
        words: Words to choose from (as from lexitron.search)
        kind: 'perfect' (the same sounds from the last stressed vowel on),
            'near' (similar sounds; see near_cost) or 'assonance' (the same
            vowels, any consonants). Near and assonance leave out perfect
            rhymes.
        exclude: Words to leave out, compared by their letters (the word
            being rhymed)
        wrenched: Match endings stressed in one and not the other instead:
            "be" and "philosophy", "window" and "go". Perfect rhymes are
            left out, and with near or assonance, perfect wrenched rhymes
            too.

    Returns:
        (word, syllables, cost) for each rhyme, cost being 0 for a perfect
        rhyme and higher the less alike it sounds. Words pronounced exactly
        like one of prons (homophones) are left out. A word's rhyming part
        may be longer than its rhyme part, if it has a stressed vowel there
        (see rhyme_tail).
    """
    prons = tuple(prons)
    parts = {rhyme_part(p) for p in prons}
    keys = {key_of(part) for part in parts}
    lengths = {syllables(part) for part in parts}
    unstressed = {p.translate(UNSTRESS) for p in prons}
    targets = wrenched_targets(prons) if wrenched else set()
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
            # The end of the word as long as each rhyme part
            tails = {n: rhyme_tail(pron, n) for n in lengths}
            perfect = any(t and key_of(t) in keys for t in tails.values())
            if kind == 'perfect' and not wrenched:
                cost = 0.0 if perfect else None
            elif perfect:
                # Perfect rhymes are listed on their own
                best = None
                break
            elif wrenched:
                cost = wrenched_cost(pron, targets, kind)
                if cost == WRENCHED_ALONE:
                    best = None
                    break
            else:
                costs = [c for c in (near_cost(target, tails[syllables(target)],
                                               kind == 'assonance')
                                     for target in parts
                                     if tails[syllables(target)]) if c is not None]
                cost = min(costs) if costs else None
            if cost is not None and (best is None or cost < best[1]):
                best = (syllables(pron), cost)
        if best:
            found.append((word, best[0], best[1]))
    return found


def wrenched_targets(prons: Iterable[str]) -> Set[Tuple[int, str, str, bool]]:
    """The endings a wrenched rhyme can match: each pronunciation's last n
    syllables, for each n up to its rhyme part's, as (n, ending, its key,
    whether its first vowel is stressed). An ending that's stressed in one
    pronunciation doesn't count as unstressed in another: "be" B IY0 is
    just "be" said quickly, and doesn't make "beat" a wrenched rhyme."""
    targets = set()
    for pron in prons:
        for n in range(1, syllables(rhyme_part(pron)) + 1):
            i = last_syllables(pron, n)
            targets.add((n, pron[i:], key_of(pron[i:]),
                         counts_as_stressed(pron, i)))
    stressed = {(n, key) for n, _, key, s in targets if s}
    return {t for t in targets if t[3] or (t[0], t[2]) not in stressed}


# What wrenched_cost gives a perfect wrenched rhyme when looking for near or
# assonant ones, which leave it out
WRENCHED_ALONE = -1.0


def wrenched_cost(pron: str, targets: Set[Tuple[int, str, str, bool]],
                  kind: str = 'perfect') -> Optional[float]:
    """How different pron sounds from the closest of the targets (see
    wrenched_targets) that it's stressed differently from, as near_cost,
    or None. For kind 'perfect' the sounds must be the same; for 'near'
    and 'assonance', a perfect wrenched rhyme gives WRENCHED_ALONE."""
    costs = []
    for n, ending, key, stressed in targets:
        i = last_syllables(pron, n)
        if i is None or counts_as_stressed(pron, i) == stressed:
            continue
        if key_of(pron[i:]) == key:
            return 0.0 if kind == 'perfect' else WRENCHED_ALONE
        if kind != 'perfect':
            cost = near_cost(ending, pron[i:], kind == 'assonance')
            if cost is not None:
                costs.append(cost)
    return min(costs) if costs else None


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


def long_cost(target: str, pron: str) -> Optional[float]:
    """How different pron sounds from target's long part, if it's a long
    rhyme for target, else None: given that their rhyme parts rhyme, the
    vowels before must be the same from target's second-to-last stressed
    vowel on, and the consonants are as alike as they come ("dedication" is
    nearer "education" than "celebration" is)."""
    part = long_part(target)
    if not part:
        return None
    tail = rhyme_tail(pron, syllables(part), long=True)
    if not tail:
        return None
    short = syllables(rhyme_part(target))
    head_a = part[:last_syllables(part, short)]
    head_b = tail[:last_syllables(tail, short)]
    (vowels_a, clusters_a), (vowels_b, clusters_b) = (split_rhyme(head_a),
                                                      split_rhyme(head_b))
    if vowels_a[0] != vowels_b[0] or any(
            x != y and not {x, y} <= REDUCED
            for x, y in zip(vowels_a[1:], vowels_b[1:])):
        return None
    return sum(cluster_cost(x, y) for x, y in zip(clusters_a, clusters_b))


def long_rhymes(prons: Iterable[str], found: List[Tuple[str, int, float]]
                ) -> Dict[str, float]:
    """The rhymes that are also long rhymes for any of prons (see
    long_cost), mapped to how different they sound."""
    prons = [p for p in prons if long_part(p)]
    result = {}
    for word, _, _ in found if prons else ():
        costs = [c for c in (long_cost(target, pron) for target in prons
                             for pron in pronunciations(word)) if c is not None]
        if costs:
            result[word] = min(costs)
    return result


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


def split_tail(text: str) -> Optional[Tuple[str, str]]:
    """Split a phrase that ends in little words (see FUNCTION_WORDS) into
    the rest and them: "hurt you" -> ("hurt", "you"), "give it to me" ->
    ("give", "it to me"); or None if it doesn't."""
    words = tokens(text)
    end = len(words)
    while end > 1 and words[end - 1] in FUNCTION_WORDS:
        end -= 1
    if end == len(words) or all(w in FUNCTION_WORDS for w in words[:end]):
        return None
    return ' '.join(words[:end]), ' '.join(words[end:])


@lru_cache(maxsize=None)
def verbs(level: int = RHYME_LEVEL) -> FrozenSet[str]:
    """Words with an -ing form up to the given SCOWL size, which are mostly
    verbs ("hurt", not "dirt")."""
    return frozenset(base for word, bases in base_forms(level).items()
                     if word.endswith('ing') for base in bases)


# Sound expressions (-S): regular expressions over pronunciations

# A run of letters (a word, or an ARPAbet phoneme in capitals, maybe with a
# stress), space, or a character of the regular expression
SOUND_TOKEN = re.compile(r"([A-Za-z']+)(\d?)|(\s+)|(.)")
SOUND_OPERATORS = set('.*+?|(){},0123456789')
BASE_PHONEMES = frozenset(CONSONANTS + VOWELS)


def vowel_class(vowel: str) -> str:
    """A regular expression for a vowel with any stress. An unstressed "ih"
    and "uh" count as the same, as the CMU Pronouncing Dictionary uses
    either for much the same sound (see REDUCE)."""
    codes = [CODE[vowel + s] for s in '012']
    other = {'AH': 'IH', 'IH': 'AH'}.get(vowel)
    if other:
        codes.append(CODE[other + '0'])
    return '[' + ''.join(re.escape(c) for c in codes) + ']'


def phoneme_regex(phoneme: str) -> str:
    """A regular expression for an ARPAbet phoneme; a vowel without a stress
    has any stress."""
    if phoneme in VOWELS:
        return vowel_class(phoneme)
    return re.escape(CODE[phoneme])


def without_stress(pron: str) -> str:
    """A pronunciation in ARPAbet without stresses, like "K AE T"."""
    return re.sub(r'\d', '', decode(pron))


def sound_regex(expression: str) -> Tuple['re.Pattern', List[Tuple[str, str]],
                                          List[str]]:
    """Turn a sound expression into a regular expression over pronunciations.

    Words stand for their sounds, whatever the stress (".*sigh"), as do
    ARPAbet phonemes in capitals (".* S AY"; "AY1" for only a stressed one);
    "." is any one sound, and *, +, ?, |, () and {} work as usual. Spaces
    only separate.

    Returns:
        The compiled expression; (word, its sounds) for each word in it, for
        -I; and notes on any pronunciations that were guessed

    Raises:
        ValueError: If a word can't be pronounced, a phoneme is wrong, or the
            expression is invalid
    """
    parts, words, notes = [], [], []
    for m in SOUND_TOKEN.finditer(expression):
        letters, stress, space, char = m.groups()
        if space:
            continue
        if char is not None:
            if char not in SOUND_OPERATORS:
                raise ValueError(f"{char!r} can't be used in a sound expression")
            parts.append(char)
        elif letters.isupper() and letters in BASE_PHONEMES:
            if stress and letters not in VOWELS:
                raise ValueError(f"only vowels have a stress, not {letters}")
            if stress and stress not in '012':
                raise ValueError(f"{letters}{stress}: a stress is 0, 1 or 2")
            parts.append(re.escape(CODE[letters + stress]) if stress
                         else phoneme_regex(letters))
        elif stress:
            raise ValueError(f"{letters}{stress} isn't an ARPAbet phoneme")
        else:
            word = letters.lower()
            prons, found_notes = pronounce_query(word)
            if not prons:
                raise ValueError(f"can't tell how to pronounce {word!r}; "
                                 "give its sounds in ARPAbet, like \"K AE T\"")
            notes += found_notes
            sounds = list(dict.fromkeys(without_stress(p) for p in prons))
            words.append((word, ' or '.join(sounds)))
            alternatives = [''.join(phoneme_regex(p) for p in s.split())
                            for s in sounds]
            parts.append('(?:' + '|'.join(alternatives) + ')')
    try:
        return re.compile(''.join(parts)), words, notes
    except re.error as e:
        raise ValueError(f"invalid sound expression: {e.msg}") from None


def sound_matches(regex: 're.Pattern', words: Iterable[str]
                  ) -> List[Tuple[str, int, float]]:
    """Find the words pronounced as a sound expression says.

    Words whose pronunciations are guesses are left out: a guess is only as
    good as the spelling it came from, and here only the sound counts.

    Returns:
        (word, syllables, 0.0) for each, like rhymes
    """
    prons, guessed = load_pronunciations()
    lookup = lambda token: () if token in guessed else prons.get(token)
    found = []
    for word in words:
        for pron in pronunciations(word, lookup):
            if regex.fullmatch(pron):
                found.append((word, syllables(pron), 0.0))
                break
    return found


# The command line

DESCRIPTION = """\
Find rhymes for a word or phrase: perfect rhymes by default, grouped by
syllables, most common first. A rhyme matches the sounds from the last
stressed vowel on, so "cat" rhymes with "acrobat". Long rhymes, which match
the vowels from the stress before too (understand, wonderland), come first;
weak rhymes (bobcat) come last. An expression, as in lx, narrows the
results: ry cat 'b.*'

With -S, find words by how they sound instead: a sound expression is like
lx's, but over sounds, with words standing for theirs: ry -S '.*sigh' ends
in the sound of "sigh". ARPAbet in capitals works too: ry -S '.* S AY'."""

EPILOG = """\
examples:
  ry orange                    near rhymes, as it has no perfect ones
  ry -N love                   near rhymes: rough, stuff, enough, ...
  ry -g -A weblog              only long ones: headlong, headstrong, ...
  ry -w be                     stress differs: philosophy, history, ...
  ry -w -A -y 2 be             and any consonants: always, carried, ...
  ry -y 2 -L 50 money          everyday two-syllable rhymes
  ry 'make it rain'            rhymes for a phrase
  ry 'hurt you'                virtue, ... and alert you, desert you, ...
  ry "K AE1 T"                 rhymes for a pronunciation (ARPAbet)
  ry -S '.*sigh'               ends in the sound of "sigh": bonsai, psi, ...
  ry -S 'sigh.*' -y 2          starts with it: cider, psychic, ...
  ry -S '.*shun.*'             has "shun" anywhere: nation, fashionable, ...
  ry -S night                  sounds exactly like "night": knight

More: <https://github.com/rothos/lexitron>"""


def make_parser() -> argparse.ArgumentParser:
    """Build the command line argument parser."""
    usage = ("ry [options] word [expression]\n"
             "       ry -S sounds [options] [expression]")
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
    parser.add_argument('-w', '--wrenched',
        dest='wrenched', action='store_true',
        help='stress differs: be, philosophy (with -N, -A too)')
    parser.add_argument('-g', '--long',
        dest='long', action='store_true',
        help='only long rhymes: understand, wonderland')
    parser.add_argument('-S', '--sounds', metavar='SOUNDS',
        dest='sounds',
        help="words by sound, not rhyme: '.*sigh', '.* S AY'")
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


def print_rhymes(sections: List[Tuple[str, List[Tuple[str, List[Tuple[str, int, float]]]]]],
                 args: argparse.Namespace, header: str, notes: List[str],
                 sizes: Dict[str, int]):
    """Print rhymes.

    Args:
        sections: (heading, groups) for each way of saying the word that
            rhymes differently ("read" as reed or red), the heading shown
            only if there's more than one; groups are (title, rhymes), like
            ("2 syllables", [...]), the title shown if there is one
        header: Describes the search, for -I
        notes: Things to mention, like a guessed pronunciation
        sizes: How common each word is, for color
    """
    words = list(dict.fromkeys(w for _, groups in sections
                               for _, found in groups for w, _, _ in found))
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
    lines = []
    for heading, groups in sections:
        if len(sections) > 1:
            lines += ['', bold(heading)] if lines or args.show_info else [bold(heading)]
        if not groups:
            lines.append(dim('none'))
            continue
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


def candidate_words(args: argparse.Namespace, expression: Optional[str],
                    ranges: Dict[str, Tuple[int, float]],
                    parser: argparse.ArgumentParser) -> List[str]:
    """The words to choose from: those the expression and filters allow."""
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
    return found['proper'] + found['common']


def print_safely(*print_args):
    """print_rhymes, exiting quietly if the reader goes away (as with
    `ry ... | head`)."""
    try:
        print_rhymes(*print_args)
        sys.stdout.flush()
    except BrokenPipeError:
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        sys.exit(1)


def find_sounds(args: argparse.Namespace, expression: Optional[str],
                ranges: Dict[str, Tuple[int, float]],
                parser: argparse.ArgumentParser):
    """ry -S: print the words pronounced as a sound expression says."""
    if args.near or args.assonance or args.wrenched or args.long:
        parser.error("-S finds words by sound, so -N, -A, -w and -g don't "
                     "go with it")
    try:
        regex, words, notes = sound_regex(args.sounds)
    except ValueError as e:
        parser.error(str(e))
    low, high = ranges.get('syllables', (0, float('inf')))
    found = [m for m in sound_matches(regex, candidate_words(
                 args, expression, ranges, parser)) if low <= m[1] <= high]
    sizes = word_sizes(95, args.base_only)
    args.weak = set()
    if args.sort == 'syllables':
        groups = [(f"{n} syllable{'s' if n != 1 else ''}",
                   ordered([m for m in found if m[1] == n], 'common', sizes))
                  for n in sorted({n for _, n, _ in found})]
    else:
        groups = [('', ordered(found, args.sort, sizes))] if found else []
    total = len(found)
    sounds = f" ({'; '.join(f'{w}: {s}' for w, s in words)})" if words else ''
    verb = 'word that sounds' if total == 1 else 'words that sound'
    header = f"{total} {verb} like '{args.sounds}'{sounds}"
    print_safely([('', groups)], args, header, notes, sizes)


def main(argv: List[str] = None):
    """Entry point for the ry command."""
    parser = make_parser()
    args = parser.parse_intermixed_args(sys.argv[1:] if argv is None else argv)

    if args.sounds is not None:
        if len(args.terms) > 1:
            parser.error("with -S, give at most an expression")
    elif not 1 <= len(args.terms) <= 2:
        parser.error("give a word (or phrase, in quotes) to rhyme, "
                     "optionally followed by an expression")

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

    if args.sounds is not None:
        find_sounds(args, args.terms[0] if args.terms else None, ranges,
                    parser)
        return
    query = args.terms[0]
    expression = args.terms[1] if len(args.terms) == 2 else None

    if args.long and args.wrenched:
        parser.error("-g and -w don't go together")

    prons, notes = pronounce_query(query)
    if not prons:
        parser.error(f"can't tell how to pronounce {query!r}; give its "
                     "pronunciation in ARPAbet instead, like \"K AE1 T\"")
    if args.long and not any(long_part(p) for p in prons):
        notes.append(f"'{query}' has no stress before its rhyme, so no long "
                     "rhymes")

    candidates = candidate_words(args, expression, ranges, parser)

    kind = 'near' if args.near else 'assonance' if args.assonance else 'perfect'
    wrenched = args.wrenched
    low, high = ranges.get('syllables', (0, float('inf')))
    # One section for each way of saying the word that rhymes differently
    by_key = {}
    for pron in prons:
        by_key.setdefault(rhyme_key(pron), []).append(pron)

    def find(kind):
        sections = []
        for group in by_key.values():
            matches = [m for m in rhymes(group, candidates, kind, [query],
                                         wrenched) if low <= m[1] <= high]
            if kind == 'near':
                matches = closest(matches)
            sections.append((group, matches))
        return sections

    # A phrase ending in little words also rhymes with words that rhyme with
    # the rest, plus the same little words: "hurt you", "desert you"
    split = None if is_arpabet(query) or args.long else split_tail(query)
    sizes = word_sizes(95, args.base_only)

    def with_tail(kind):
        if not split:
            return []
        head, tail = split
        head_prons = pronounce_query(head)[0]
        tail_syllables = syllables(pronunciations(tail)[0])
        heads = [w for w in candidates if not re.search(r'[\s-]', w)]
        if tail.split()[0] in OBJECTS:
            heads = [w for w in heads if w.lower() in verbs(args.level)]
        found = rhymes(head_prons, heads, kind, [head], wrenched)
        if kind == 'near':
            found = closest(found)
        weak = weak_rhymes([w for w, _, _ in found], head_prons, head)
        result = []
        for w, n, cost in found:
            if low <= n + tail_syllables <= high:
                phrase = f"{w} {tail}"
                sizes[phrase] = sizes.get(w, 100)
                result.append((phrase, n + tail_syllables, cost))
                if w in weak:
                    weaklings.add(phrase)
        return result

    def weak(sections, kind):
        return weak_rhymes([w for _, found in sections for w, _, _ in found],
                           prons, query,
                           inflections=kind != 'perfect' or wrenched)

    weaklings = set()
    sections, phrases = find(kind), with_tail(kind)
    if kind == 'perfect' and not wrenched:
        everything = {w for _, found in sections for w, _, _ in found}
        weak_words = weak(sections, kind)
        if not everything - weak_words and len(phrases) <= len(weaklings):
            only = f" but {', '.join(sorted(weak_words))}" if weak_words else ''
            notes.append(f"no perfect rhymes for '{query}'{only}; "
                         "showing near rhymes")
            kind = 'near'
            weaklings = set()
            sections, phrases = find(kind), with_tail(kind)

    # Weak rhymes go last, dimmed
    args.weak = weak(sections, kind) | weaklings
    good = {w for _, found in sections for w, _, _ in found} - args.weak
    # With few perfect rhymes, show near rhymes too, unless they were
    # narrowed down on purpose
    narrowed = expression is not None or any((args.syllables, args.length,
        args.include, args.exclude, args.pattern))
    # (and not when piped, where they'd be mixed in unlabeled)
    plain = args.unformatted or not sys.stdout.isatty()
    near = (find('near') if kind == 'perfect' and not wrenched
            and not args.long and len(good) < FEW and not narrowed and not plain else None)
    if near:
        args.weak |= weak(near, 'near')

    def by_syllables(found):
        if args.sort != 'syllables':
            return [('', ordered(found, args.sort, sizes, args.weak))] if found else []
        counts = sorted({n for _, n, _ in found})
        return [(f"{n} syllable{'s' if n != 1 else ''}",
                 ordered([m for m in found if m[1] == n], args.sort, sizes,
                         args.weak)) for n in counts]

    def flat(title, found):
        order = 'common' if args.sort == 'syllables' else args.sort
        return [(title, ordered(found, order, sizes, args.weak))] if found else []

    output = []
    # "wrenched near", or nothing for perfect rhymes
    label = ' '.join(['wrenched'] * wrenched + [kind] * (kind != 'perfect'))
    for i, (group, found) in enumerate(sections):
        groups = []
        # Long rhymes first: they rhyme from the stress before too
        lengths = long_rhymes(group, found) if not wrenched else {}
        if lengths:
            longs = [(w, n, lengths[w]) for w, n, _ in found if w in lengths]
            if args.sort == 'alpha':
                groups += flat('long rhymes', longs)
            else:
                # The closest, then the rest, most common first
                groups.append(('long rhymes', sorted(longs, key=lambda m: (
                    m[0] in args.weak, m[2] > LONG_CLOSE,
                    sizes.get(m[0], 100), m[0].lower()))))
            found = [m for m in found if m[0] not in lengths]
        if not args.long:
            groups += by_syllables(found)
        if near and near[i][1]:
            # Closest first
            groups.append(('near rhymes', sorted(near[i][1], key=lambda m: (
                m[0] in args.weak, round(m[2], 1), sizes.get(m[0], 100),
                m[0].lower()))))
        if i == len(sections) - 1 and phrases:
            title = (f"{label}: " if label else '') + f"… {split[1]}"
            groups += flat(title, phrases)
        heading = f"{query} ({' or '.join(decode(p) for p in group)})"
        output.append((heading, groups))

    total = len({w for _, groups in output for _, found in groups
                 for w, _, _ in found})
    noun = {'perfect': 'rhyme', 'near': 'near rhyme',
            'assonance': 'assonant word'}[kind]
    if wrenched:
        noun = 'wrenched ' + noun
    elif args.long:
        noun = 'long ' + noun
    header = (f"{total} {noun}{'' if total == 1 else 's'} for '{query}' "
              f"({' or '.join(decode(p) for p in prons)})")

    print_safely(output, args, header, notes, sizes)

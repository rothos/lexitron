"""Lexitron, a command-line regex search engine for the English language."""

import sys, os, re, gzip, argparse, shutil
from collections import Counter
from functools import lru_cache
from importlib import resources, metadata
from math import ceil, floor, log2
from typing import Dict, List, Optional, Tuple

WORDLIST = 'words.tsv.gz'
DEFAULT_LEVEL = 70
# Wordle answers are everyday words
WORDLE_LEVEL = 50
# How many of the best, and of the worst, guesses --probes lists
PROBES_SHOWN = 20
SORT_ORDERS = ('family', 'alpha', 'length', 'common', 'best')
# Terminal style for inflections listed after their base form
DIM, RESET = '\033[2m', '\033[0m'
ESCAPE_CODE = re.compile('\033\\[[0-9;]*m')
# Terminal colors for other words by SCOWL size, from common (bold green)
# through yellow to obscure (red): each applies up to and including its size
SIZE_STYLES = [
    (35, '\033[1;38;5;34m'),
    (40, '\033[38;5;70m'),
    (50, '\033[38;5;142m'),
    (60, '\033[38;5;178m'),
    (70, '\033[38;5;208m'),
    (95, '\033[38;5;160m'),
]
FORMATTING = {
    'gutter_width': 4,
    'terminal_margin': 1,
}


# Each entry is a (word, size, base_size, base_forms) tuple:
#   size:       how obscure the word is, 35 (core) ... 95
#   base_size:  its size as a base form, or None if it is only inflected
#   base_forms: comma-separated words it is an inflection of, e.g. "go"
# See scripts/build_wordlist.py.
Entry = Tuple[str, int, Optional[int], str]


@lru_cache(maxsize=None)
def load_words(level: int = 95) -> List[Entry]:
    """Load the bundled word list, up to the given SCOWL size."""
    with resources.files('lexitron').joinpath(WORDLIST).open('rb') as f:
        text = gzip.decompress(f.read()).decode('ascii')

    # This runs on every invocation, so it avoids per-field work where it
    # can. The file is sorted by size, so stop at the first word above level;
    # a word's base size is never smaller than its size.
    sizes = {str(n): n for n in range(100)}
    sizes['-'] = None
    words = []
    for line in text.split('\n'):
        if not line or line.startswith('#'):
            continue
        word, size, base_size, base_forms = line.split('\t')
        size = sizes[size]
        if size > level:
            break
        words.append((word, size, sizes[base_size], base_forms))
    return words


@lru_cache(maxsize=None)
def word_sizes(level: int = 95, base_only: bool = False) -> Dict[str, int]:
    """Map each word, up to the given SCOWL size, to its size.

    With base_only, use each word's size as a base form.
    """
    return {word: base_size if base_only else size
            for word, size, base_size, _ in load_words(level)}


@lru_cache(maxsize=None)
def base_forms(level: int = 95) -> Dict[str, List[str]]:
    """Map each inflected word, up to the given SCOWL size, to its base forms."""
    return {word: forms.split(',') for word, _, _, forms in load_words(level)
            if forms}


def families(words: List[str], level: int = 95) -> Dict[str, str]:
    """Map each inflected word to the base form it's listed under.

    A word is listed under its first base form that is also in words
    ("ran" under "run"), unless it has inflections of its own there ("rung"
    stays with "rungs" rather than going under "ring"). Words not in the
    result head their own family.
    """
    present = set(words)
    forms = base_forms(level)
    parents = {}
    for word in words:
        parent = next((base for base in forms.get(word, ())
                       if base in present and base != word), None)
        if parent:
            parents[word] = parent
    for parent in set(parents.values()):
        parents.pop(parent, None)
    return parents


def letters_of(text: str) -> str:
    """The letters in a word or phrase, lowercased."""
    return ''.join(c for c in text.lower() if c.isalpha())


def parse_length(spec: str) -> Tuple[int, float]:
    """Parse a length like "5", "4-7", "5-" or "-7" into (min, max)."""
    match = re.fullmatch(r'(\d*)(-?)(\d*)', spec.strip())
    if not match or not (match[1] or match[3]) or (match[1] and match[3] and not match[2]):
        raise ValueError(f"invalid length: {spec!r}")
    low, dash, high = match.groups()
    if not dash:
        return int(low), int(low)
    return int(low or 0), int(high) if high else float('inf')


BLANK = '.'


def letters_matcher(letters: str, anagram: bool = False, repeat: bool = False):
    """Return a function testing whether a word can be made from letters.

    Args:
        letters: The letters available; "." is a blank, standing for
            any one letter
        anagram: The word must use every letter, blanks included
        repeat: Letters may be used more than once; each blank adds one
            letter of the word's choosing
    """
    available = Counter(letters_of(letters))
    blanks = letters.count(BLANK)

    def matches(word: str) -> bool:
        used = Counter(letters_of(word))
        if anagram and available - used:
            return False
        if repeat:
            return len(used.keys() - available.keys()) <= blanks
        # Letters the word needs beyond what's available, filled by blanks
        missing = sum((used - available).values())
        return missing == blanks if anagram else missing <= blanks

    return matches


def include_matcher(letters: str):
    """Return a function testing whether a word contains all of letters,
    each at least as often as given ("ee" needs two e's)."""
    needed = Counter(letters_of(letters))
    return lambda word: not needed - Counter(letters_of(word))


def exclude_matcher(letters: str):
    """Return a function testing whether a word contains none of letters."""
    banned = set(letters_of(letters))
    return lambda word: banned.isdisjoint(letters_of(word))


def pattern_matcher(pattern: str):
    """Return a function testing whether a word has the shape of pattern.

    Each character of the pattern is a placeholder: the same character means
    the same letter, different characters mean different letters, and "."
    is any letter. So "abba" matches "deed" and "a.a.a" matches "rarer".
    """
    pattern = pattern.lower()

    def matches(word: str) -> bool:
        letters = letters_of(word)
        if len(letters) != len(pattern):
            return False
        assigned = {}
        for slot, letter in zip(pattern, letters):
            if slot == '.':
                continue
            if assigned.setdefault(slot, letter) != letter:
                return False
        return len(set(assigned.values())) == len(assigned)

    return matches


def parse_wordle(spec: str) -> Tuple[str, str]:
    """Parse a Wordle guess like "crane:..y.g" into (guess, result).

    In the result, g is green (right letter, right place), y is yellow
    (in the word, elsewhere) and . is grey (not in the word).
    """
    guess, colon, result = spec.lower().partition(':')
    if not colon or not guess.isalpha() or len(guess) != len(result) \
            or set(result) - set('gy.'):
        raise ValueError(f"invalid Wordle guess {spec!r}: use the guess, a "
                         "colon, then g, y or . for each letter, like "
                         "crane:..y.g")
    return guess, result


def wordle_matcher(guesses: List[Tuple[str, str]]):
    """Return a function testing whether a word fits Wordle feedback.

    Args:
        guesses: (guess, result) pairs, as from parse_wordle
    """
    rules = []
    for guess, result in guesses:
        # Letters marked green or yellow are in the word at least that many
        # times; a grey copy of the same letter means exactly that many.
        marked = Counter(c for c, r in zip(guess, result) if r != '.')
        greyed = {c for c, r in zip(guess, result) if r == '.'}
        counts = {c: (marked[c], c in greyed) for c in set(guess)}
        rules.append((guess, result, counts))

    def matches(word: str) -> bool:
        if not word.isalpha():
            return False
        word = word.lower()
        for guess, result, counts in rules:
            if len(word) != len(guess):
                return False
            for c, w, r in zip(guess, word, result):
                if (r == 'g') != (c == w):
                    return False
            for c, (n, exact) in counts.items():
                found = word.count(c)
                if found < n or (exact and found != n):
                    return False
        return True

    return matches


EDITS = ('plus', 'minus', 'change', 'hooks')


def parse_edit(spec: str) -> Tuple[str, int]:
    """Parse a word with an optional letter count, like "cat" or "cat:2"."""
    word, colon, count = spec.partition(':')
    word = letters_of(word)
    if not word or (colon and not count.isdigit()) or count == '0':
        raise ValueError(f"invalid word {spec!r}: use a word, optionally "
                         "followed by a colon and a number, like cat:2")
    return word, int(count) if colon else 1


def is_subsequence(short: str, long: str) -> bool:
    """Whether short's letters appear in long, in order."""
    letters = iter(long)
    return all(c in letters for c in short)


def edit_matcher(kind: str, word: str, count: int = 1):
    """Return a function testing whether a word is an edit of word.

    Args:
        kind: 'plus' (count letters inserted anywhere), 'minus' (count
            letters removed), 'change' (count letters swapped for others) or
            'hooks' (one letter added at the front or back)
    """
    word = letters_of(word)

    def matches(other: str) -> bool:
        if not other.isalpha():
            return False
        other = other.lower()
        if kind == 'plus':
            return len(other) == len(word) + count and is_subsequence(word, other)
        if kind == 'minus':
            return len(other) == len(word) - count and is_subsequence(other, word)
        if kind == 'change':
            return len(other) == len(word) and \
                sum(a != b for a, b in zip(word, other)) == count
        return len(other) == len(word) + 1 and word in (other[1:], other[:-1])

    return matches


def hooks(word: str, words: List[str]) -> Tuple[str, str]:
    """The letters that hook onto word, at the front and the back, given
    the words that hook it (as found by edit_matcher('hooks', word))."""
    word = letters_of(word)
    found = [letters_of(w) for w in words]
    front = sorted({w[0] for w in found if w[1:] == word})
    back = sorted({w[-1] for w in found if w[:-1] == word})
    return ''.join(front), ''.join(back)


def search(expression: str = '.*', substring: bool = False,
           base_only: bool = False, case_sensitive: bool = False,
           common: bool = True, proper: bool = False,
           level: int = DEFAULT_LEVEL, phrases: bool = False,
           single_words: bool = True,
           length: Optional[Tuple[int, float]] = None,
           letters: Optional[str] = None, anagram: bool = False,
           repeat: bool = False, include: Optional[str] = None,
           exclude: Optional[str] = None, pattern: Optional[str] = None,
           wordle: Optional[List[Tuple[str, str]]] = None,
           edit: Optional[Tuple[str, str, int]] = None,
           sort: str = 'family') -> Dict[str, List[str]]:
    """Search the word list.

    Args:
        expression: Regular expression to search for
        substring: Match anywhere within a word, rather than the whole word
        base_only: Search only base forms, not their inflected forms
        case_sensitive: Match uppercase and lowercase letters exactly
        common: Include common (all-lowercase) words
        proper: Include proper words (containing uppercase, like "France")
        level: Include words up to this SCOWL size (35 core ... 95 obscure)
        phrases: Include entries with spaces or hyphens
        single_words: Include entries without spaces or hyphens
        length: (min, max) number of letters
        letters: Only words that can be spelled with these letters
        anagram: With letters, the word must use every letter
        repeat: With letters, letters may be used more than once
        include: Only words containing all of these letters, each at least
            as often as given
        exclude: Only words containing none of these letters
        pattern: Only words with this shape, e.g. "abba" for "deed"; see
            pattern_matcher
        wordle: Only words fitting these Wordle (guess, result) pairs; see
            parse_wordle
        edit: Only words that are an edit of a word: a (kind, word, count)
            tuple; see edit_matcher
        sort: 'family' (alphabetical, with inflections after their base
            form), 'alpha', 'length' (shortest first), 'common' (most
            common first) or 'best' (best Wordle guess first; see
            best_order)

    Returns:
        Dictionary with 'common' and 'proper' lists of matching words

    Raises:
        re.error: If the expression is not a valid regular expression
    """
    flags = 0 if case_sensitive else re.IGNORECASE
    expr = re.compile(expression, flags=flags)

    # By default the expression must match the whole word.
    matcher = expr.search if substring else expr.fullmatch
    tests = []
    if letters:
        tests.append(letters_matcher(letters, anagram, repeat))
    if include:
        tests.append(include_matcher(include))
    if exclude:
        tests.append(exclude_matcher(exclude))
    if pattern:
        tests.append(pattern_matcher(pattern))
    if wordle:
        tests.append(wordle_matcher(wordle))
    if edit:
        tests.append(edit_matcher(*edit))

    matches = {'common': [], 'proper': []}
    for word, size, base_size, _ in load_words(level):
        if base_only:
            size = base_size
        if size is None or size > level:
            continue
        if not (phrases if ' ' in word or '-' in word else single_words):
            continue

        kind = 'common' if word.islower() else 'proper'
        if not (common if kind == 'common' else proper):
            continue

        if length and not length[0] <= len(letters_of(word)) <= length[1]:
            continue
        if not all(test(word) for test in tests):
            continue
        if matcher(word):
            matches[kind].append((word, size))

    sort_key = {
        'family': lambda m: m[0],
        'alpha':  lambda m: m[0],
        'length': lambda m: (len(letters_of(m[0])), m[0]),
        'common': lambda m: (m[1], m[0]),
        # Ties in best_order go to the more common word
        'best':   lambda m: (m[1], m[0]),
    }[sort]
    results = {kind: [word for word, _ in sorted(found, key=sort_key)]
               for kind, found in matches.items()}
    if sort == 'best':
        results = {kind: best_order(words) for kind, words in results.items()}
    if sort == 'family' and not base_only:
        results = {kind: family_order(words, level)
                   for kind, words in results.items()}
    return results


def wordle_result(guess: str, answer: str) -> str:
    """The Wordle result for a guess, like "..y.g" (see parse_wordle).

    A repeated letter in the guess is colored only as many times as it's in
    the answer, greens first.
    """
    # This runs for every pair of words in best_order, so it's kept lean.
    if guess == answer:
        return 'g' * len(guess)
    unmatched = [a for g, a in zip(guess, answer) if g != a]
    result = ''
    for g, a in zip(guess, answer):
        if g == a:
            result += 'g'
        elif g in unmatched:
            result += 'y'
            unmatched.remove(g)
        else:
            result += '.'
    return result


def best_order(words: List[str]) -> List[str]:
    """Reorder words by how good a Wordle guess each is, if any of them
    could be the answer.

    A guess is scored by how evenly its results would split the words: the
    expected information (entropy) of the result, in bits. Words of other
    lengths count as one more group. Python's sort is stable, so ties keep
    their order.
    """
    lowered = tuple(w.lower() for w in words)
    scores = guess_scores(lowered, lowered)
    return sorted(words, key=lambda w: -scores[w.lower()])


@lru_cache(maxsize=None)
def guess_scores(guesses: Tuple[str, ...],
                 answers: Tuple[str, ...]) -> Dict[str, float]:
    """Map each lowercase guess to how many bits of information it would
    give, if any of the lowercase answers could be the answer (see
    best_order)."""
    n = len(answers)

    def score(guess):
        groups = Counter(wordle_result(guess, answer)
                         if len(answer) == len(guess) else len(answer)
                         for answer in answers)
        # + 0.0 turns -0.0 into 0.0
        return -sum(k / n * log2(k / n) for k in groups.values()) + 0.0

    return {guess: score(guess) for guess in set(guesses)}


def best_probes(answers: List[str], guesses: List[str], limit: int = 10,
                better_only: bool = True) -> List[Tuple[str, float]]:
    """The best guesses other than the answers, with their scores in bits.

    These are Wordle guesses that can't be right, but may narrow things down
    better than a guess that could be.

    Args:
        better_only: Only guesses that would give more information than any
            of the answers
    """
    answers = tuple(w.lower() for w in answers)
    if not answers:
        return []
    others = tuple(w for w in guesses if w not in set(answers))
    scores = guess_scores(others, answers).items()
    if better_only:
        top = max(guess_scores(answers, answers).values())
        scores = [(w, score) for w, score in scores if score > top + 1e-9]
    return sorted(scores, key=lambda m: (-m[1], m[0]))[:limit]


def family_order(words: List[str], level: int = 95) -> List[str]:
    """Reorder sorted words so inflections follow their base form."""
    parents = families(words, level)
    children = {}
    for word in words:
        if word in parents:
            children.setdefault(parents[word], []).append(word)
    ordered = []
    for word in words:
        if word not in parents:
            ordered.append(word)
            ordered += children.get(word, [])
    return ordered


def header(commons: List[str], propers: List[str], description: str,
           breakdown: bool = False) -> str:
    """Generate header string showing search results summary.

    Args:
        commons: List of matching common words
        propers: List of matching proper words
        description: What was searched for, e.g. "/.*icide/"
        breakdown: Whether to show the proper/common counts

    Returns:
        Header string
    """
    total = len(commons) + len(propers)
    noun = 'match' if total == 1 else 'matches'
    txt = f"{total} {noun} for {description}"
    if breakdown:
        txt += f" ({len(propers)} proper, {len(commons)} common)"
    return txt


def formatted(words: List[str], termwidth: int, termheight: int,
              styles: Optional[Dict[str, str]] = None) -> str:
    """Format word list into columns that fit the terminal dimensions.

    Args:
        words: List of words to format
        termwidth: Width of terminal in characters
        termheight: Height of terminal in characters
        styles: Terminal escape codes to show some words in, e.g. DIM

    Returns:
        String of words formatted in columns
    """
    N = len(words)
    GUTTER = FORMATTING['gutter_width']
    # Words may contain terminal escape codes, which take up no room
    lengths = {word: len(ESCAPE_CODE.sub('', word)) for word in words}
    COLWIDTH = max(lengths.values())

    # Adjust terminal width by margin
    termwidth = termwidth - FORMATTING['terminal_margin']

    # The maximum number of columns that will fit in the terminal
    # (taking into account gutter width). The mathematics:
    #    termwidth = n*colwidth + (n-1)*gutter,   solve for n.
    max_num_cols = max(1, floor((GUTTER + termwidth)/float(GUTTER + COLWIDTH)))

    # These are heuristics for determining the number of columns of output.
    num_cols = int(max(1, min(max_num_cols, ceil(N/(termheight/2.)))))
    num_rows = int(ceil(N/float(num_cols)))

    # Fill in the rest of the matrix with blanks.
    words = words + ['']*(num_cols*num_rows - N)

    styles = styles or {}
    def cell(word):
        padding = ' '*(COLWIDTH + GUTTER - lengths.get(word, 0))
        if word in styles:
            return styles[word] + word + RESET + padding
        return word + padding

    rowlist = []
    for k in range(num_rows):
        rowlist += [''.join(cell(word) for word in words[k::num_rows]).rstrip()]

    return '\n'.join(rowlist)


def size_style(size: int) -> str:
    """The terminal color for a word of this SCOWL size."""
    return next(style for limit, style in SIZE_STYLES if size <= limit)


def styles(words: List[str], level: int = 95,
           base_only: bool = False) -> Dict[str, str]:
    """Color words by how common they are, and dim inflected forms listed
    under a base form (unless base_only)."""
    sizes = word_sizes(level, base_only)
    found = {}
    for word in words:
        size = sizes.get(word)
        if size is not None:
            found[word] = size_style(size)
    if not base_only:
        found.update((word, DIM) for word in families(words, level))
    return found


def use_color() -> bool:
    """Whether to style output, following <https://no-color.org>."""
    return not os.environ.get('NO_COLOR') and os.environ.get('TERM') != 'dumb'


def print_results(matches: Dict[str, List[str]], args: argparse.Namespace,
                  description: str):
    """Print search results according to specified format.

    Args:
        matches: Dictionary containing lists of matching common and proper words
        args: Parsed arguments controlling output format
        description: What was searched for, for the header
    """
    commons = matches['common']
    propers = matches['proper']
    info = header(commons, propers, description, args.include_proper)

    # Fall back to one word per line when output isn't a terminal
    if args.unformatted or not sys.stdout.isatty():
        # The header goes to stderr so stdout stays machine-readable
        if args.show_info:
            print(info, file=sys.stderr)

        if args.number:
            print(len(propers + commons))
        elif propers or commons:
            print('\n'.join(propers + commons))
        return

    width, height = shutil.get_terminal_size()
    width = width - 1  # Wiggle room

    if args.number:
        # The header already includes the number
        print(info if args.show_info else len(propers + commons))
        return

    if args.show_info:
        print(info)
        if propers or commons:
            print()

    if args.edit and args.edit[0] == 'hooks':
        # Scrabble style: front hooks, the word, back hooks
        front, back = hooks(args.edit[1], propers + commons)
        print(f"{front or '-'}  {args.edit[1]}  {back or '-'}")
        return

    def show(words, probes=()):
        if args.sort == 'best':
            show_scored(words, probes)
            return
        styled = (styles(words, args.level, args.base_only)
                  if use_color() else None)
        print(formatted(words, width, height, styled))

    def show_scored(words, probes):
        # Each word with its bits, best first. Probes (which can't be the
        # answer) are dimmed, or starred without color; on a tie the word
        # that could be the answer comes first. With --probes, a "..." row
        # separates the best probes from the worst.
        lowered = tuple(w.lower() for w in words)
        scores = args.scores or guess_scores(lowered, lowered)
        ranked = [(w, scores[w.lower()], False) for w in words]
        ranked += [(w, score, True) for w, score in probes]
        ranked.sort(key=lambda m: -m[1])
        color = use_color()
        # Color by commonness, but don't dim families: dim means a probe
        sizes = word_sizes(args.level, args.base_only)
        width_ = max(len(w) for w, _, _ in ranked)
        cells = []
        for word, score, probe in ranked:
            bits = f"{score:.2f}"
            if not color:
                cells.append(f"{word:<{width_}} {bits}" + ('*' if probe else ''))
                continue
            # The word in its color, the bits dimmed
            style = DIM if probe else size_style(sizes[word]) \
                if word in sizes else ''
            padding = ' ' * (width_ - len(word))
            cells.append(f"{style}{word}{RESET}{padding} {DIM}{bits}{RESET}")
        if args.gap:
            cells.insert(args.gap, '...')
        print(formatted(cells, width, height))

    if propers:
        show(propers)
    if commons and propers:
        print()
    if commons:
        show(commons, getattr(args, 'probes', ()))


def version() -> str:
    try:
        return metadata.version('lexitron')
    except metadata.PackageNotFoundError:
        return 'unknown'


DESCRIPTION = """\
Lexitron searches English words with regular expressions. The expression must
match the whole word, and by default only common (lowercase) words are
searched."""

EPILOG = """\
expressions, letters and patterns:
  The same characters mean different things in different places.
  In an EXPRESSION they're regex: . is any letter, x? is an optional x,
  .* is any run of letters, [abc] is one of a, b or c.
      lx 'dot?'                 do, dot
  In LETTERS (with -f or -a), each letter is a tile and . is a blank.
      lx -a dot.                dote, doth, toad, ...
  In a PATTERN (-t), each letter stands for some letter, the same throughout.
      lx -t abba                abba, boob, deed, ...
  Quote expressions so the shell leaves *, ? and $ alone.

examples:
  lx '.*icide'                  words ending in "icide"
  lx -s rdb                     words containing "rdb"
  lx -a listen                  anagrams of "listen"
  lx -l 4- -rf eihnglw -s h     Spelling Bee, center letter h
  lx -i q -e u                  words with a q but no u
  lx -w crane:..y.g             Wordle: a yellow, e green, c r n grey
  lx --hooks cat                letters that hook onto "cat"

More examples: <https://github.com/rothos/lexitron>"""


def make_parser() -> argparse.ArgumentParser:
    """Build the command line argument parser."""
    usage = "lx [options] [expression]\n" +\
        "       lx -f|-a [options] letters [expression]"
    parser = argparse.ArgumentParser(prog='lx', usage=usage,
        description=DESCRIPTION, epilog=EPILOG, add_help=False,
        formatter_class=argparse.RawDescriptionHelpFormatter)

    # The positional arguments: an expression, or with -f/-a, letters and an
    # optional expression. Letters are positional rather than an option value
    # so -f and -a can be bundled with other flags in any order (-rf, -fr).
    parser.add_argument('terms', nargs='*', metavar='[letters] expression',
        help='a regular expression the whole word must match; with -f or -a, '
             'first the letters to spell from')

    group = parser.add_argument_group('how the expression matches')
    group.add_argument('-s', '--substring',
        dest='substring', action='store_true',
        help='match anywhere within a word, rather than the whole word')
    group.add_argument('-c', '--case-sensitive',
        dest='case_sensitive', action='store_true',
        help='match uppercase and lowercase letters exactly')

    group = parser.add_argument_group('spelling from letters')
    letters = group.add_mutually_exclusive_group()
    letters.add_argument('-f', '--from',
        dest='from_letters', action='store_true',
        help='only words spelled from the letters, each used at most as '
             'often as given; . is a blank tile, standing for any letter')
    letters.add_argument('-a', '--anagram',
        dest='anagram', action='store_true',
        help='only words that use exactly the letters, blanks included')
    group.add_argument('-r', '--repeat',
        dest='repeat', action='store_true',
        help='with -f or -a, letters may be used any number of times')

    group = parser.add_argument_group('more filters')
    group.add_argument('-l', '--length', metavar='N',
        dest='length',
        help='only words with this many letters: 5, 4-7, 5- or -7')
    group.add_argument('-i', '--include', metavar='LETTERS',
        dest='include',
        help='only words containing all of these letters; repeats count, so '
             'ee means at least two e\'s')
    group.add_argument('-e', '--exclude', metavar='LETTERS',
        dest='exclude',
        help='only words containing none of these letters')
    group.add_argument('-t', '--pattern', metavar='PATTERN',
        dest='pattern',
        help='only words with this shape: each letter stands for a letter, '
             'the same letter for the same letter and different letters for '
             'different ones, and . for any letter; a.a.a matches "rarer"')

    group = parser.add_argument_group('word games')
    group.add_argument('-w', '--wordle', metavar='GUESS:RESULT',
        dest='wordle', action='append',
        help='Wordle: the guess, then g (green), y (yellow) or . (grey) for '
             'each letter, like crane:..y.g; repeat for each guess. Sets the '
             'length, the level to 50 and the sort to best, unless -L or -o '
             'is given. In a terminal, shows bits of information for each '
             'guess, and dims guesses that can\'t be the answer but would '
             'narrow things down more')
    group.add_argument('--probes',
        dest='probes_only', action='store_true',
        help=f'with -w, list only guesses that can\'t be the answer: the '
             f'{PROBES_SHOWN} that would narrow things down most, then the '
             f'{PROBES_SHOWN} that would narrow them down least')
    edits = group.add_mutually_exclusive_group()
    edits.add_argument('--plus', metavar='WORD[:N]',
        help='words made by inserting a letter (or N letters) anywhere in '
             'the word: cat -> cart, chat, coat, ...')
    edits.add_argument('--minus', metavar='WORD[:N]',
        help='words made by removing a letter (or N): cart -> art, car, cat')
    edits.add_argument('--change', metavar='WORD[:N]',
        help='words made by changing one letter (or N), as in word ladders: '
             'cat -> bat, cot, car, ...')
    edits.add_argument('--hooks', metavar='WORD',
        help='Scrabble hooks: the letters that go on the front or back of '
             'the word to make another word')

    group = parser.add_argument_group('which words to search')
    group.add_argument('-L', '--level', metavar='N',
        dest='level', type=int,
        help='include words up to this obscurity level: 35 (core), 50, 60 '
             '(standard dictionary), 70 (large dictionary, the default), 80, '
             '95 (everything)')
    group.add_argument('-b', '--base-only',
        dest='base_only', action='store_true',
        help='leave out inflected forms like plurals and conjugations')
    phrases = group.add_mutually_exclusive_group()
    phrases.add_argument('-p', '--phrases',
        dest='phrases', action='store_true',
        help='include entries with spaces or hyphens, like "sperm whale"')
    phrases.add_argument('-P', '--phrases-only',
        dest='only_phrases', action='store_true',
        help='search only entries with spaces or hyphens')
    proper = group.add_mutually_exclusive_group()
    proper.add_argument('-u', '--uppercase',
        dest='include_proper', action='store_true',
        help='include proper words with capitals, like "France"')
    proper.add_argument('-U', '--uppercase-only',
        dest='only_proper', action='store_true',
        help='search only proper words with capitals')

    group = parser.add_argument_group('output')
    group.add_argument('-o', '--sort', metavar='ORDER',
        dest='sort', choices=SORT_ORDERS,
        help='family (the default: alphabetical, with inflections like '
             'plurals right after their base form), alpha, length (shortest '
             'first), common (most common first) or best (best Wordle guess '
             'first, the default with -w)')
    group.add_argument('-n', '--number-only',
        dest='number', action='store_true',
        help='print only the number of matches')
    group.add_argument('-I', '--info',
        dest='show_info', action='store_true',
        help='print a header describing the search')
    group.add_argument('-x', '--plain',
        dest='unformatted', action='store_true',
        help='print one word per line, without columns or color')
    group.add_argument('-h', '--help',
        action='help',
        help='print this help and exit')
    group.add_argument('-v', '--version',
        action='version', version="Lexitron " + version(),
        help='print version and exit')

    return parser


def describe(args: argparse.Namespace) -> str:
    """Describe a search for the info header, e.g. "/.*s/ from 'aerst'"."""
    parts = []
    if args.expression is not None:
        parts.append(f"/{args.expression}/")
    if args.letters is not None:
        kind = 'anagram of' if args.anagram else 'from'
        parts.append(f"{kind} '{args.letters}'")
    if args.include:
        parts.append(f"containing '{args.include}'")
    if args.exclude:
        parts.append(f"without '{args.exclude}'")
    if args.pattern:
        parts.append(f"shaped '{args.pattern}'")
    if args.wordle:
        parts.append("Wordle " + ', '.join(args.wordle))
        if args.probes_only:
            parts.append("(probes)")
    if args.edit:
        kind, word, count = args.edit
        letter = 'letter' if count == 1 else f'{count} letters'
        parts.append({
            'plus': f"'{word}' plus {letter}",
            'minus': f"'{word}' minus {letter}",
            'change': f"'{word}' with {letter} changed",
            'hooks': f"hooks of '{word}'",
        }[kind])
    if args.length:
        parts.append(f"length {args.length}")
    return ' '.join(parts)


# The function that will be called from the command line
def main(argv: List[str] = None):
    """Entry point for the Lexitron command line interface."""
    parser = make_parser()
    # Intermixed, so options can go between the letters and the expression:
    # lx -rf eihnglw -l 4- '.*h.*'
    args = parser.parse_intermixed_args(sys.argv[1:] if argv is None else argv)

    args.edit = None
    for kind in EDITS:
        spec = getattr(args, kind)
        if spec is not None:
            try:
                word, count = parse_edit(spec)
            except ValueError as e:
                parser.error(str(e))
            if kind == 'hooks' and ':' in spec:
                parser.error("--hooks takes a word without a number")
            args.edit = (kind, word, count)

    if args.probes_only and not args.wordle:
        parser.error("--probes only works with -w")

    wordle = None
    if args.wordle:
        try:
            wordle = [parse_wordle(spec) for spec in args.wordle]
        except ValueError as e:
            parser.error(str(e))

    # Sort out the positional arguments. The expression can be left out when
    # another option says what to look for.
    args.letters = args.expression = None
    if args.from_letters or args.anagram:
        if not 1 <= len(args.terms) <= 2:
            parser.error("-f and -a take letters, optionally followed by an expression")
        args.letters = args.terms[0]
        if '?' in args.letters:
            parser.error("in letters, a blank tile is . rather than ?")
        if len(args.terms) == 2:
            args.expression = args.terms[1]
    else:
        filtered = (args.length or args.include or args.exclude
                    or args.pattern or wordle or args.edit)
        if len(args.terms) > 1:
            parser.error("expected one expression")
        if not args.terms and not filtered:
            parser.error("an expression is required")
        if args.terms:
            args.expression = args.terms[0]
        if args.repeat:
            parser.error("-r only works with -f or -a")

    length = None
    if args.length:
        try:
            length = parse_length(args.length)
        except ValueError as e:
            parser.error(str(e))

    if args.level is None:
        args.level = WORDLE_LEVEL if wordle else DEFAULT_LEVEL
    if args.sort is None:
        args.sort = 'best' if wordle else 'family'

    try:
        matches = search(
            '.*' if args.expression is None else args.expression,
            substring=args.substring,
            base_only=args.base_only,
            case_sensitive=args.case_sensitive,
            common=not args.only_proper,
            proper=args.include_proper or args.only_proper,
            level=args.level,
            phrases=args.phrases or args.only_phrases,
            single_words=not args.only_phrases,
            length=length,
            letters=args.letters,
            anagram=args.anagram,
            repeat=args.repeat,
            include=args.include,
            exclude=args.exclude,
            pattern=args.pattern,
            wordle=wordle,
            edit=args.edit,
            sort=args.sort)
    except re.error as e:
        parser.error(f"invalid regular expression: {e}")

    # Wordle guesses that can't be right but would narrow things down more,
    # shown among the results in a terminal
    args.probes, args.scores, args.gap = [], None, None
    show_probes = args.sort == 'best' and sys.stdout.isatty() \
        and not (args.unformatted or args.number)
    if wordle and (show_probes or args.probes_only):
        size = len(wordle[0][0])
        guesses = search('[a-z]+', level=args.level, length=(size, size),
                         sort='alpha')['common']
        if args.probes_only:
            # The best and worst probes take the place of the results,
            # scored against them
            probes = best_probes(matches['common'], guesses, None,
                                 better_only=False)
            if len(probes) > 2 * PROBES_SHOWN:
                probes = probes[:PROBES_SHOWN] + probes[-PROBES_SHOWN:]
                args.gap = PROBES_SHOWN
            matches = {'common': [w for w, _ in probes], 'proper': []}
            args.scores = dict(probes)
        else:
            args.probes = best_probes(matches['common'], guesses)

    try:
        print_results(matches, args, describe(args))
        sys.stdout.flush()
    except BrokenPipeError:
        # The reader went away (e.g. `lx ... | head`); exit quietly.
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        sys.exit(1)

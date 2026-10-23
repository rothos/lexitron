"""Lexitron, a command-line regex search engine for the English language."""

import sys, os, re, gzip, argparse, shutil
from collections import Counter
from functools import lru_cache
from importlib import resources, metadata
from math import ceil, floor
from typing import Dict, List, Optional, Tuple

WORDLIST = 'words.tsv.gz'
DEFAULT_LEVEL = 70
SORT_ORDERS = ('family', 'alpha', 'length', 'common')
# Terminal style for inflections listed after their base form
DIM, RESET = '\033[2m', '\033[0m'
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


BLANKS = '?.'


def letters_matcher(letters: str, anagram: bool = False, repeat: bool = False):
    """Return a function testing whether a word can be made from letters.

    Args:
        letters: The letters available; "?" or "." is a blank, standing for
            any one letter
        anagram: The word must use every letter, blanks included
        repeat: Letters may be used more than once; each blank adds one
            letter of the word's choosing
    """
    available = Counter(letters_of(letters))
    blanks = sum(letters.count(blank) for blank in BLANKS)

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


def search(expression: str = '.*', substring: bool = False,
           base_only: bool = False, case_sensitive: bool = False,
           common: bool = True, proper: bool = False,
           level: int = DEFAULT_LEVEL, phrases: bool = False,
           single_words: bool = True,
           length: Optional[Tuple[int, float]] = None,
           letters: Optional[str] = None, anagram: bool = False,
           repeat: bool = False, sort: str = 'family') -> Dict[str, List[str]]:
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
        sort: 'family' (alphabetical, with inflections after their base
            form), 'alpha', 'length' (shortest first) or 'common' (most
            common first)

    Returns:
        Dictionary with 'common' and 'proper' lists of matching words

    Raises:
        re.error: If the expression is not a valid regular expression
    """
    flags = 0 if case_sensitive else re.IGNORECASE
    expr = re.compile(expression, flags=flags)

    # By default the expression must match the whole word.
    matcher = expr.search if substring else expr.fullmatch
    fits_letters = letters_matcher(letters, anagram, repeat) if letters else None

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
        if fits_letters and not fits_letters(word):
            continue
        if matcher(word):
            matches[kind].append((word, size))

    sort_key = {
        'family': lambda m: m[0],
        'alpha':  lambda m: m[0],
        'length': lambda m: (len(letters_of(m[0])), m[0]),
        'common': lambda m: (m[1], m[0]),
    }[sort]
    results = {kind: [word for word, _ in sorted(found, key=sort_key)]
               for kind, found in matches.items()}
    if sort == 'family' and not base_only:
        results = {kind: family_order(words, level)
                   for kind, words in results.items()}
    return results


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
    COLWIDTH = max([len(word) for word in words])

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
        padding = ' '*(COLWIDTH + GUTTER - len(word))
        if word in styles:
            return styles[word] + word + RESET + padding
        return word + padding

    rowlist = []
    for k in range(num_rows):
        rowlist += [''.join(cell(word) for word in words[k::num_rows]).rstrip()]

    return '\n'.join(rowlist)


def styles(words: List[str], level: int = 95,
           base_only: bool = False) -> Dict[str, str]:
    """Color words by how common they are, and dim inflected forms listed
    under a base form."""
    sizes = word_sizes(level, base_only)
    found = {}
    for word in words:
        size = sizes.get(word)
        if size is not None:
            found[word] = next(style for limit, style in SIZE_STYLES
                               if size <= limit)
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

    def show(words):
        styled = (styles(words, args.level, args.base_only)
                  if use_color() else None)
        print(formatted(words, width, height, styled))

    if propers:
        show(propers)
    if commons and propers:
        print()
    if commons:
        show(commons)


def version() -> str:
    try:
        return metadata.version('lexitron')
    except metadata.PackageNotFoundError:
        return 'unknown'


def make_parser() -> argparse.ArgumentParser:
    """Build the command line argument parser."""
    description = "Lexitron, a regex search engine for the English " +\
        "language. By default, Lexitron searches only for common " +\
        "(lowercase) words."
    epilog = "The expression must match the whole word; use -s to " +\
        "match anywhere within a word instead. Searches are " +\
        "case-insensitive unless -c is given. See " +\
        "<https://github.com/rothos/lexitron> for further " +\
        "documentation and examples."
    usage = "lx [options] expression\n" +\
        "       lx -f|-a [options] letters [expression]"
    parser = argparse.ArgumentParser(prog='lx', usage=usage,
        description=description, epilog=epilog)

    # The positional arguments: an expression, or with -f/-a, letters and an
    # optional expression. Letters are positional rather than an option value
    # so -f and -a can be bundled with other flags in any order (-rf, -fr).
    parser.add_argument('terms', nargs='*', metavar='[letters] expression',
        help='the regular expression to search; with -f or -a, the letters '
             'to use, optionally followed by an expression')

    # What to match
    parser.add_argument('-s', '--substring',
        dest='substring', action='store_true',
        help='match the expression anywhere within a word, rather than the whole word')
    parser.add_argument('-c', '--case-sensitive',
        dest='case_sensitive', action='store_true',
        help='match uppercase and lowercase letters exactly')
    parser.add_argument('-l', '--length', metavar='N',
        dest='length',
        help='only words with this many letters: 5, 4-7, 5- or -7')
    letters = parser.add_mutually_exclusive_group()
    letters.add_argument('-f', '--from',
        dest='from_letters', action='store_true',
        help='only words spelled from the given letters, each used at most '
             'as often as given; ? or . is a blank, standing for any letter')
    letters.add_argument('-a', '--anagram',
        dest='anagram', action='store_true',
        help='only words that use exactly the given letters')
    parser.add_argument('-r', '--repeat',
        dest='repeat', action='store_true',
        help='with -f or -a, letters may be used any number of times')

    # Which words to search
    parser.add_argument('-b', '--base-only',
        dest='base_only', action='store_true',
        help='search only base forms, not inflected forms like plurals and conjugations')
    parser.add_argument('-L', '--level', metavar='N',
        dest='level', type=int, default=DEFAULT_LEVEL,
        help='include words up to this obscurity level: 35 (core), 50, 60 '
             '(standard dictionary), 70 (large dictionary, the default), 80, '
             '95 (everything)')
    phrases = parser.add_mutually_exclusive_group()
    phrases.add_argument('-p', '--phrases',
        dest='phrases', action='store_true',
        help='include entries with spaces or hyphens, like "sperm whale"')
    phrases.add_argument('-P', '--only-phrases',
        dest='only_phrases', action='store_true',
        help='search only entries with spaces or hyphens')
    proper = parser.add_mutually_exclusive_group()
    proper.add_argument('-u', '--uppercase',
        dest='include_proper', action='store_true',
        help='include uppercase/proper words (like "France") in addition to lowercase/common words')
    proper.add_argument('-U', '--only-uppercase',
        dest='only_proper', action='store_true',
        help='search only for uppercase/proper words')

    # Output
    parser.add_argument('-i', '--info',
        dest='show_info', action='store_true',
        help='print info header along with search results')
    parser.add_argument('-n', '--number-only',
        dest='number', action='store_true',
        help='print only the total number of matches')
    parser.add_argument('-o', '--sort', metavar='ORDER',
        dest='sort', choices=SORT_ORDERS, default='family',
        help='sort by family (the default: alphabetical, with inflections '
             'like plurals and conjugations right after their base form), '
             'alpha, length (shortest first) or common (most common first)')
    parser.add_argument('-x', '--plain',
        dest='unformatted', action='store_true',
        help='print unformatted output, one word per line')
    parser.add_argument('-v', '--version',
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
    return ' '.join(parts)


# The function that will be called from the command line
def main(argv: List[str] = None):
    """Entry point for the Lexitron command line interface."""
    parser = make_parser()
    # Intermixed, so options can go between the letters and the expression:
    # lx -rf eihnglw -l 4- '.*h.*'
    args = parser.parse_intermixed_args(sys.argv[1:] if argv is None else argv)

    # Sort out the positional arguments
    args.letters = args.expression = None
    if args.from_letters or args.anagram:
        if not 1 <= len(args.terms) <= 2:
            parser.error("-f and -a take letters, optionally followed by an expression")
        args.letters = args.terms[0]
        if len(args.terms) == 2:
            args.expression = args.terms[1]
    else:
        if len(args.terms) != 1:
            parser.error("expected one expression" if args.terms
                         else "an expression is required")
        args.expression = args.terms[0]
        if args.repeat:
            parser.error("-r only works with -f or -a")

    length = None
    if args.length:
        try:
            length = parse_length(args.length)
        except ValueError as e:
            parser.error(str(e))

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
            sort=args.sort)
    except re.error as e:
        parser.error(f"invalid regular expression: {e}")

    try:
        print_results(matches, args, describe(args))
        sys.stdout.flush()
    except BrokenPipeError:
        # The reader went away (e.g. `lx ... | head`); exit quietly.
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        sys.exit(1)

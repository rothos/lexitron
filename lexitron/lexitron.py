"""Lexitron, a command-line regex search engine for the English language."""

import sys, os, re, gzip, argparse, shutil
from collections import Counter
from functools import lru_cache
from importlib import resources, metadata
from math import ceil, floor
from typing import Dict, List, Optional, Tuple

WORDLIST = 'words.tsv.gz'
DEFAULT_LEVEL = 70
SORT_ORDERS = ('alpha', 'length', 'common')
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


def letters_matcher(letters: str, anagram: bool = False, repeat: bool = False):
    """Return a function testing whether a word can be made from letters.

    Args:
        letters: The letters available
        anagram: The word must use every letter
        repeat: Letters may be used more than once
    """
    available = Counter(letters_of(letters))

    def matches(word: str) -> bool:
        used = Counter(letters_of(word))
        if repeat:
            return used.keys() == available.keys() if anagram \
                else used.keys() <= available.keys()
        return used == available if anagram else not (used - available)

    return matches


def search(expression: str = '.*', substring: bool = False,
           base_only: bool = False, case_sensitive: bool = False,
           common: bool = True, proper: bool = False,
           level: int = DEFAULT_LEVEL, phrases: bool = False,
           length: Optional[Tuple[int, float]] = None,
           letters: Optional[str] = None, anagram: bool = False,
           repeat: bool = False, sort: str = 'alpha') -> Dict[str, List[str]]:
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
        length: (min, max) number of letters
        letters: Only words that can be spelled with these letters
        anagram: With letters, the word must use every letter
        repeat: With letters, letters may be used more than once
        sort: 'alpha', 'length' (shortest first) or 'common' (most common first)

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
        if not phrases and (' ' in word or '-' in word):
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
        'alpha':  lambda m: m[0],
        'length': lambda m: (len(letters_of(m[0])), m[0]),
        'common': lambda m: (m[1], m[0]),
    }[sort]
    return {kind: [word for word, _ in sorted(found, key=sort_key)]
            for kind, found in matches.items()}


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


def formatted(words: List[str], termwidth: int, termheight: int) -> str:
    """Format word list into columns that fit the terminal dimensions.

    Args:
        words: List of words to format
        termwidth: Width of terminal in characters
        termheight: Height of terminal in characters

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

    rowlist = []
    for k in range(num_rows):
        rowlist += [''.join(word.ljust(COLWIDTH+GUTTER) \
                    for word in words[k::num_rows]).rstrip()]

    return '\n'.join(rowlist)


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

    if propers:
        print(formatted(propers, width, height))
    if commons and propers:
        print()
    if commons:
        print(formatted(commons, width, height))


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
    parser = argparse.ArgumentParser(prog='lx',
        description=description, epilog=epilog)

    # Add the positional argument
    parser.add_argument('expression', type=str, nargs='?',
        help='the regular expression to search (optional with -f or -a)')

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
    letters.add_argument('-f', '--from', metavar='LETTERS',
        dest='letters',
        help='only words spelled from these letters, each used at most as often as given')
    letters.add_argument('-a', '--anagram', metavar='LETTERS',
        dest='anagram',
        help='only words that use exactly these letters')
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
    parser.add_argument('-p', '--phrases',
        dest='phrases', action='store_true',
        help='include entries with spaces or hyphens, like "sperm whale"')
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
        dest='sort', choices=SORT_ORDERS, default='alpha',
        help='sort by alpha (the default), length (shortest first) or '
             'common (most common first)')
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
    if args.letters:
        parts.append(f"from '{args.letters}'")
    if args.anagram:
        parts.append(f"anagram of '{args.anagram}'")
    return ' '.join(parts)


# The function that will be called from the command line
def main(argv: List[str] = None):
    """Entry point for the Lexitron command line interface."""
    parser = make_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)

    if args.expression is None and not (args.letters or args.anagram):
        parser.error("an expression is required unless -f or -a is given")
    if args.repeat and not (args.letters or args.anagram):
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
            phrases=args.phrases,
            length=length,
            letters=args.letters or args.anagram,
            anagram=bool(args.anagram),
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

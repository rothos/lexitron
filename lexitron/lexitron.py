import sys, os, re, argparse, shutil
from importlib import resources, metadata
from math import ceil, floor
from typing import Dict, List, Tuple

class Lexitron:
    """Main class for the Lexitron command line tool."""

    # Configuration constants
    DEFAULT_ENCODING = 'utf-8'
    WORDLIST_PATHS = {
        'common': 'agid-common.txt',
        'proper': 'agid-proper.txt'
    }
    # AGID marks questionable or machine-generated forms with these
    # characters, e.g. "culpabler?" or "abdominocentesisses<?"
    QUESTIONABLE_FORM = re.compile(r'[?!~<]')
    ANNOTATION = re.compile(r'\{.*?\}')
    FORMATTING = {
        'gutter_width': 4,
        'terminal_margin': 1,
        'show_rules': False
    }

    def __init__(self):
        """Initialize Lexitron with wordlist files and argument parser configuration."""
        # The wordlist files
        self.wordlist_common_file = resources.files('lexitron').joinpath(self.WORDLIST_PATHS['common'])
        self.wordlist_proper_file = resources.files('lexitron').joinpath(self.WORDLIST_PATHS['proper'])

        # Here is the argument parser
        description = "Lexitron, a regex search engine for the English " +\
            "language. By default, Lexitron searches only for common " +\
            "(lowercase) words."
        epilog = "The expression must match the whole word; use -s to " +\
            "match anywhere within a word instead. Searches are " +\
            "case-insensitive unless -c is given. See " +\
            "<https://github.com/rothos/lexitron> for further " +\
            "documentation and examples."
        self.parser = argparse.ArgumentParser(prog='lx',
            description=description, epilog=epilog)

        # Add the positional argument
        self.parser.add_argument('expression', type=str,
            help='the regular expression to search')

        # Add the optional arguments
        self.parser.add_argument('-b', '--base-only',
            dest='base_only', action='store_true',
            help='search only base forms, not inflected forms like plurals and conjugations')
        self.parser.add_argument('-c', '--case-sensitive',
            dest='case_sensitive', action='store_true',
            help='match uppercase and lowercase letters exactly')
        self.parser.add_argument('-n', '--number-only',
            dest='number', action='store_true',
            help='print only the total number of matches')
        self.parser.add_argument('-i', '--info',
            dest='show_info', action='store_true',
            help='print info header along with search results')
        self.parser.add_argument('-s', '--substring',
            dest='substring', action='store_true',
            help='match the expression anywhere within a word, rather than the whole word')
        proper = self.parser.add_mutually_exclusive_group()
        proper.add_argument('-u', '--uppercase',
            dest='include_proper', action='store_true',
            help='include uppercase/proper words (like "France") in addition to lowercase/common words')
        proper.add_argument('-U', '--only-uppercase',
            dest='only_proper', action='store_true',
            help='search only for uppercase/proper words')
        self.parser.add_argument('-v', '--version',
            action='version', version="Lexitron "+metadata.version('lexitron'),
            help='print version and exit')
        self.parser.add_argument('-x', '--plain',
            dest='unformatted', action='store_true',
            help='print unformatted output, one word per line')

    def print_help(self):
        """Display the help message for the command line interface."""
        self.parser.print_help()

    def parse_args(self, argv: List[str]) -> argparse.Namespace:
        """Parse command line arguments.

        Args:
            argv: List of command line arguments

        Returns:
            Parsed argument namespace
        """
        # Parse the incoming arguments
        args = self.parser.parse_args(argv)
        return args

    def search(self, expression: str, substring: bool = False,
               base_only: bool = False, case_sensitive: bool = False,
               common: bool = True, proper: bool = False) -> Dict[str, List[str]]:
        """Search wordlists for matches to the given regular expression.

        Args:
            expression: Regular expression to search for
            substring: Match anywhere within a word, rather than the whole word
            base_only: Search only headwords, not their inflected forms
            case_sensitive: Match uppercase and lowercase letters exactly
            common: Search the common (lowercase) wordlist
            proper: Search the proper (uppercase) wordlist

        Returns:
            Dictionary with 'common' and 'proper' lists of matching words

        Raises:
            re.error: If the expression is not a valid regular expression
        """
        flags = 0 if case_sensitive else re.IGNORECASE
        expr = re.compile(expression, flags=flags)
        matches = {'common': [], 'proper': []}

        # By default the expression must match the whole word.
        matcher = expr.search if substring else expr.fullmatch

        # Now open each requested wordlist and start searching.
        wordlists = [('common', common, self.wordlist_common_file),
                     ('proper', proper, self.wordlist_proper_file)]
        for kind, wanted, wordlist_file in wordlists:
            if wanted:
                for word in self._iter_words(wordlist_file, base_only):
                    if matcher(word):
                        matches[kind].append(word)

        matches['common'] = sorted(list(set(matches['common'])))
        matches['proper'] = sorted(list(set(matches['proper'])))

        return matches

    def _iter_words(self, wordlist_file, base_only: bool = False) -> str:
        """Iterate through words in a wordlist file.

        Args:
            wordlist_file: A Path object pointing to the wordlist file
            base_only: Whether to yield only headwords, not inflected forms

        Yields:
            str: Each word from the file, one at a time
        """
        with wordlist_file.open('rb') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith(b'#'):  # Skip empty lines and comments
                    yield from self.parse_line(line, base_only)

    def parse_line(self, line: bytes, base_only: bool = False) -> List[str]:
        """Parse a line from the wordlist file.

        Lines look like "run V: ran | run | running | runs", where forms are
        separated by "|" (one slot per inflection) and "," (alternatives).
        A form may be followed by a variant level ("travelled 1") or an
        annotation ("oxes {oaf}").

        Args:
            line: A line from the wordlist file
            base_only: Whether to return only the headword

        Returns:
            The headword, followed by its inflected forms unless base_only
        """
        head, _, forms = line.decode().partition(':')
        words = [head.split()[0]]

        if not base_only:
            for form in re.split(r'[|,]', self.ANNOTATION.sub('', forms)):
                form = form.split()
                if form and not self.QUESTIONABLE_FORM.search(form[0]):
                    words.append(form[0])

        return words

    def print_results(self, matches: Dict[str, List[str]], args: argparse.Namespace):
        """Print search results according to specified format.

        Args:
            matches: Dictionary containing lists of matching common and proper words
            args: Parsed arguments controlling output format
        """
        commons = matches['common']
        propers = matches['proper']

        # Fall back to one word per line when output isn't a terminal
        if args.unformatted or not sys.stdout.isatty():
            # The header goes to stderr so stdout stays machine-readable
            if args.show_info:
                print(self.header(commons, propers, args), file=sys.stderr)

            if args.number:
                # Unformatted number only
                print(str(len(propers + commons)))
            else:
                # Unformatted matches
                if propers or commons:
                    print('\n'.join(propers + commons))
        else:
            width, height = shutil.get_terminal_size()
            width = width - 1  # Wiggle room

            if args.number:
                # The header already includes the number
                if args.show_info:
                    print(self.header(commons, propers, args, width))
                else:
                    print(len(propers + commons))
            else:
                # Print header if requested
                if args.show_info:
                    print(self.header(commons, propers, args, width))
                    if propers or commons:
                        print()

                # Print matches
                if propers:
                    print(self.formatted(propers, width, height))
                if commons and propers:
                    print()
                if commons:
                    print(self.formatted(commons, width, height))

    def header(self, commons: List[str], propers: List[str], args: argparse.Namespace, width: int = 0) -> str:
        """Generate header string showing search results summary.

        Args:
            commons: List of matching common words
            propers: List of matching proper words
            args: Parsed arguments containing search expression
            width: Terminal width for formatting

        Returns:
            Formatted header string
        """
        rule = '-' * width if self.FORMATTING['show_rules'] else ''
        total = len(commons + propers)
        noun = 'match' if total == 1 else 'matches'
        expr = args.expression

        breakdown = ''
        if args.include_proper:
            breakdown = ' (' + str(len(propers)) + ' proper, ' + str(len(commons)) + ' common)'

        if self.FORMATTING['show_rules']:
            txt = "{rule}\n{total} {noun} for /{expr}/{breakdown}\n{rule}"
        else:
            txt = "{total} {noun} for /{expr}/{breakdown}"

        return txt.format(rule=rule, total=total, noun=noun, expr=expr, breakdown=breakdown)

    def formatted(self, words: List[str], termwidth: int, termheight: int) -> str:
        """Format word list into columns that fit the terminal dimensions.

        Args:
            words: List of words to format
            termwidth: Width of terminal in characters
            termheight: Height of terminal in characters

        Returns:
            String of words formatted in columns
        """
        N = len(words)
        GUTTER = self.FORMATTING['gutter_width']
        COLWIDTH = max([len(word) for word in words])

        # Adjust terminal width by margin
        termwidth = termwidth - self.FORMATTING['terminal_margin']

        # The maximum number of columns that will fit in the terminal
        # (taking into account gutter width). The mathematics:
        #    termwidth = n*colwidth + (n-1)*gutter,   solve for n.
        max_num_cols = max(1, floor((GUTTER + termwidth)/float(GUTTER + COLWIDTH)))

        # These are heuristics for determining the number of columns of output.
        num_cols = max(1, min(max_num_cols, ceil(N/(termheight/2.))))
        num_rows = ceil(N/float(num_cols))

        # Convert to integers.
        num_cols = int(num_cols)
        num_rows = int(num_rows)

        # Fill in the rest of the matrix with blanks.
        # words = words + ['']*((numcols - (n-numcols*numrows)) % numcols)
        words = words + ['']*(num_cols*num_rows - N)

        rowlist = []
        for k in range(num_rows):
            rowlist += [''.join(word.ljust(COLWIDTH+GUTTER) \
                        for word in words[k::num_rows]).rstrip()]

        pretty_printed_results = '\n'.join(rowlist)
        return pretty_printed_results


# The function that will be called from the command line
def main(argv: List[str] = None):
    """Entry point for the Lexitron command line interface."""
    lx   = Lexitron()
    args = lx.parse_args(sys.argv[1:] if argv is None else argv)

    try:
        matches = lx.search(args.expression,
            substring=args.substring,
            base_only=args.base_only,
            case_sensitive=args.case_sensitive,
            common=not args.only_proper,
            proper=args.include_proper or args.only_proper)
    except re.error as e:
        lx.parser.error(f"invalid regular expression: {e}")

    try:
        lx.print_results(matches, args)
        sys.stdout.flush()
    except BrokenPipeError:
        # The reader went away (e.g. `lx ... | head`); exit quietly.
        devnull = os.open(os.devnull, os.O_WRONLY)
        os.dup2(devnull, sys.stdout.fileno())
        sys.exit(1)

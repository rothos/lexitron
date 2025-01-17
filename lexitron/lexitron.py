import sys, os, re, argparse
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
        epilog = "Currently, Lexitron only allows case-insensitive " +\
            "searching.\n\nSee <https://github.com/rothos/lexitron> for " +\
            "further documentation and examples."
        self.parser = argparse.ArgumentParser(prog='lx',
            description=description, epilog=epilog)

        # Add the positional argument
        self.parser.add_argument('expression', type=str,
            help='the regular expression to search')

        # Add the optional arguments
        self.parser.add_argument('-n', '--number-only',
            dest='number', action='store_true',
            help='print only the total number of matches')
        self.parser.add_argument('-i', '--info',
            dest='show_info', action='store_true',
            help='print info header along with search results')
        self.parser.add_argument('-u', '--uppercase',
            dest='include_proper', action='store_true',
            help='include uppercase/proper words (like "France") in addition to lowercase/common words')
        self.parser.add_argument('-U', '--only-uppercase',
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

    def search(self, args: argparse.Namespace) -> Dict[str, List[str]]:
        """Search wordlists for matches to the given regular expression.
        
        Args:
            args: Parsed command line arguments containing search parameters
            
        Returns:
            Dictionary with 'common' and 'proper' lists of matching words
        """
        # Get the expression ready.
        expr = self.sanitize(args.expression)

        # Currently, lexitron search is case-insensitive.
        expr = re.compile(expr, flags=re.IGNORECASE)
        matches = {'common': [], 'proper': []}

        # Now open each wordlist and start searching.
        # Always search common words unless only_proper is specified
        if not args.only_proper:
            for word in self._iter_words(self.wordlist_common_file):
                if expr.search(word):
                    matches['common'].append(word)

        # Only search proper words if include_proper or only_proper is specified
        if args.include_proper or args.only_proper:
            for word in self._iter_words(self.wordlist_proper_file):
                if expr.search(word):
                    matches['proper'].append(word)

        matches['common'] = sorted(list(set(matches['common'])))
        matches['proper'] = sorted(list(set(matches['proper'])))

        return matches

    def sanitize(self, expr: str) -> str:
        """Remove wrapping quotation marks from the input expression.
        
        Args:
            expr: Regular expression string
            
        Returns:
            Sanitized expression string
        """
        # Remove any wrapping quotation marks from the input.
        if expr[0]  in ('"',"'"): expr = expr[1:]
        if expr[-1] in ('"',"'"): expr = expr[:-1]
        return expr

    def _iter_words(self, wordlist_file) -> str:
        """Iterate through words in a wordlist file.
        
        Args:
            wordlist_file: A Path object pointing to the wordlist file
            
        Yields:
            str: Each word from the file, one at a time
        """
        with wordlist_file.open('rb') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith(b'#'):  # Skip empty lines and comments
                    try:
                        yield self.parse_line(line)
                    except LexitronParseError:
                        continue  # Skip lines that can't be parsed

    def parse_line(self, line: bytes) -> str:
        """Parse a line from the wordlist file.
        
        Args:
            line: A line from the wordlist file
            
        Returns:
            The word from the line
        """
        # This only returns the word right now, but since the agid.txt list
        # contains other information (part of speech, derivative words, etc),
        # the search may become more robust in the future.
        try:
            return line.split()[0].decode()
        except (IndexError, UnicodeDecodeError) as e:
            raise LexitronParseError(f"Failed to parse line: {e}")

    def print_results(self, matches: Dict[str, List[str]], args: argparse.Namespace):
        """Print search results according to specified format.
        
        Args:
            matches: Dictionary containing lists of matching common and proper words
            args: Parsed arguments controlling output format
        """
        commons = matches['common']
        propers = matches['proper']

        if args.unformatted:
            if args.number:
                # Unformatted number only
                print(str(len(propers + commons)))
            else:
                # Unformatted matches
                print('\n'.join(propers + commons))
        else:
            width, height = os.get_terminal_size()
            width = width - 1  # Wiggle room

            if args.number:
                # Print only the total number
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

    def header(self, commons: List[str], propers: List[str], args: argparse.Namespace, width: int) -> str:
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
        expr = self.sanitize(args.expression)

        breakdown = ''
        if args.include_proper and not args.only_proper:
            breakdown = ' (' + str(len(propers)) + ' proper, ' + str(len(commons)) + ' common)'

        if self.FORMATTING['show_rules']:
            txt = "{rule}\n{total} matches for /{expr}/{breakdown}\n{rule}"
        else:
            txt = "{total} matches for /{expr}/{breakdown}"
            
        return txt.format(rule=rule, total=total, expr=expr, breakdown=breakdown)

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


# This is invoked when there's an error parsing the wordlist files
class LexitronParseError(Exception):
    pass


# The function that will be called from the command line
def main():
    """Entry point for the Lexitron command line interface."""
    lx      = Lexitron()
    args    = lx.parse_args(sys.argv[1:])
    matches = lx.search(args)
    lx.print_results(matches, args)

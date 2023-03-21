import sys, os, re, argparse
from importlib import resources, metadata
from math import ceil, floor

class Lexitron:
    def __init__(self):
        # The wordlist files
        self.wordlist_common_file = resources.files('lexitron').joinpath('agid-common.txt')
        self.wordlist_proper_file = resources.files('lexitron').joinpath('agid-proper.txt')

        with self.wordlist_common_file.open('rb') as f:
            self.wordlist_common = f.read()
        f.close()

        with self.wordlist_proper_file.open('rb') as f:
            self.wordlist_proper = f.read()
        f.close()

        # Here is the argument parser
        description = "Lexitron, a regex search engine for the English " +\
            "language."
        epilog = "Currently, Lexitron only allows case-insensitive " +\
            "searching.\n\nSee <http://github.com/rothos/lexitron> for " +\
            "further documentation and examples."
        self.parser = argparse.ArgumentParser(prog='lx',
            description=description, epilog=epilog)

        # Add the positional argument
        self.parser.add_argument('expression', type=str,
            help='The regular expression to search')

        # Add the optional arguments
        # self.parser.add_argument('-a',
        #     dest='all', action='store_true',
        #     help='Search all words, including plurals and conjugations')
        self.parser.add_argument('-n', '--number-only',
            dest='number', action='store_true',
            help='Print only the number of matches')
        self.parser.add_argument('-u', '--lowercase',
            dest='only_common', action='store_true',
            help='Search only for lowercase/common/uncapitalized words (like "boat")')
        self.parser.add_argument('-U', '--uppercase',
            dest='only_proper', action='store_true',
            help='Search only for uppercase/proper/capitalized words (like "France")')
        self.parser.add_argument('-v', '--version',
            action='version', version="Lexitron "+metadata.version('lexitron'),
            help='Show version and exit')
        self.parser.add_argument('-x', '--plain',
            dest='unformatted', action='store_true',
            help='Print unformatted output, one word per line')

    def print_help(self):
        self.parser.print_help()

    def parse_args(self, argv):
        # Parse the incoming arguments
        args = self.parser.parse_args(argv)
        return args

    def search(self, args):
        # Figure out which files to search
        if args.only_common and args.only_proper:
            msg = 'Mutually exclusive options -u and -U may not ' \
                + 'be used together.'
            raise LexitronOptionsError(msg)

        # Currently, lexitron search is case-insensitive.
        expr = re.compile(expr, flags=re.IGNORECASE)
        matches = {'common': [], 'proper': []}

        # Now open each wordlist and start searching.
        if not args.only_proper:
            for line in self.wordlist_common.splitlines():
                word = self.parse_line(line)
                if expr.search(word):
                    matches['common'] += [word]

        if not args.only_common:
            for line in self.wordlist_proper.splitlines():
                word = self.parse_line(line)
                if expr.search(word):
                    matches['proper'] += [word]

        matches['common'] = sorted(list(set(matches['common'])))
        matches['proper'] = sorted(list(set(matches['proper'])))

        return matches

    def sanitize(self, expr):
        # Remove any wrapping quotation marks from the input.
        if expr[0]  in ('"',"'"): expr = expr[1:]
        if expr[-1] in ('"',"'"): expr = expr[:-1]
        return expr

    def parse_line(self, line):
        # This only returns the word right now, but since the agid.txt list
        # contains other information (part of speech, derivative words, etc),
        # the search may become more robust in the future.
        return line.split()[0].decode()

    def print_results(self, matches, args):
        commons = matches['common']
        propers = matches['proper']

        if args.unformatted:
            if args.number:
                # Unformatted number
                print(str(len(propers + commons)))
            else:
                # Unformatted matches
                print('\n'.join(propers + commons))

        else:
            width, height = os.get_terminal_size()
            width  = width - 1  # Wiggle room

            if args.number:
                # Formatted number
                print(self.header(commons, propers, args, width))
            else:
                # Formatted matches
                print(self.header(commons, propers, args, width))
                if propers:
                    print(self.formatted(propers, width, height))
                if commons:
                    print(self.formatted(commons, width, height))

    def header(self, commons, propers, args, width):
        rule  = '-' * width
        total = len(commons + propers)
        expr  = self.sanitize(args.expression)

        breakdown = [str(len(propers)) + ' proper', str(len(commons)) + ' common']
        if args.only_proper:
            breakdown = ['(restricted search)']
        elif args.only_common:
            breakdown = ['(restricted search)']
        breakdown = ' ~ '.join(breakdown)

        txt = "{rule}\n{total} results for /{expr}/\n" \
              "{breakdown}\n{rule}\n".format(rule=rule,
                total=total, expr=expr, breakdown=breakdown)

        return txt

    def formatted(self, words, termwidth, termheight):
        n        = len(words)
        gutter   = 4
        colwidth = max([len(word) for word in words])

        # The maximum number of columns that will fit in the terminal
        # (taking into account gutter width). The mathematics:
        #    termwidth = n*colwidth + (n-1)*gutter,   solve for n.
        maxnumcols = max(1, floor((gutter + termwidth)/float(gutter + colwidth)))

        # These are heuristics for determining the number of columns of output.
        numcols = max(1, min(maxnumcols, ceil(n/(termheight/2.))))
        numrows = ceil(n/float(numcols))

        # Convert to integers.
        numcols = int(numcols)
        numrows = int(numrows)

        # Fill in the rest of the matrix with blanks.
        # words = words + ['']*((numcols - (n-numcols*numrows)) % numcols)
        words = words + ['']*(numcols*numrows - n)

        rowlist = []
        for k in range(numrows):
            rowlist += [''.join(word.ljust(colwidth+gutter) \
                        for word in words[k::numrows]).rstrip()]

        pretty_printed_results = '\n'.join(rowlist) + '\n'
        return pretty_printed_results


# This is invoked when mutually exclusive options -a and -A are used together.
class LexitronOptionsError(Exception):
    pass


# The function that will be called from the command line
def main():
    lx      = Lexitron()
    args    = lx.parse_args(sys.argv[1:])
    matches = lx.search(args)
    lx.print_results(matches, args)

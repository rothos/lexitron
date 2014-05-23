#!/usr/bin/python
"""\
Lexitron

A regex search engine for the English language.

Usage: $ python lexitron.py [options] [expression]
   or: $ alias lx='python ~/path/wordfinder.py'
       $ lx [options] [expression]

Options:
  -h           show this help
  -d           debug mode
  -u           print unformatted text (comma-separated list of words)
  -x           do not print the results (only the header)
  -p           proper words only
  -n           common words only
  -c           case-sensitive search
  -g           global search; ie. the expression can be
                    matched anywhere inside the word

To-do:
    fix non-english characters (eg. e`, o`)

"""

import sys
import getopt
import re
from math import ceil

def main(argv):
    global _dictionary
    global _terminalwidth
    global _debug
    _dictionary     = 'wordlists/common'
    _terminalwidth  = 80
    _debug          = 0
    ugly            = 0
    printstuff      = 1
    do_props        = 1
    do_imps         = 1
    casesense       = 0 # not case-sensitive by default
    globalsearch    = 0 # strict search by default
    exp = ''

    opts, args = getopt.getopt(argv, "hduxcpngw:")

    if not (opts or args):
        usage()
        sys.exit()

    for opt, arg in opts:
        if opt == '-h':
            usage()
            sys.exit()
        elif opt == '-d':
            _debug = 1
        elif opt == '-u':
            ugly = 1
        elif opt == '-x':
            printstuff = 0
        elif opt == '-c':
            casesense = 1
        elif opt == '-p':
            do_imps = 0
        elif opt == '-n':
            do_props = 0
        elif opt == '-g':
            globalsearch = 1
        elif opt == '-w':
            _terminalwidth = int(arg[1:])
        else:
            usage()
            sys.exit()

    exp = args[0]
    results = search(exp, globalsearch, casesense) # searcharoo
    props, imps = counts(results) # categorizearoo
    if not do_props: props = []
    if not do_imps:  imps  = []

    # print the header
    print(header(exp, props, imps, opts))

    # print the results
    if results and printstuff:
        tab = max([len(w) for w in results])
        if props: print(wordcols(props, tab, ugly))
        if imps:  print(wordcols(imps, tab, ugly))

def search(exp, globalsearch, casesense):
    exp = sanitize(exp)
    if not globalsearch: exp = "^" + exp + "$" # impose the strict condition if need be

    words = open(_dictionary).read().split('\n')
    words = [w for w in words if w and w[-2:] != "'s"] # get rid of the possessives

    if casesense: pattern = re.compile(exp)
    else:         pattern = re.compile(exp, flags=re.IGNORECASE)
    results = [w for w in words if pattern.search(w)]
    return results

def sanitize(exp):
    if exp[0]  in ('"',"'"): exp = exp[1:]
    if exp[-1] in ('"',"'"): exp = exp[:-1]
    return exp

# separate proper nouns from common words
def counts(results):
    props = [w for w in results if w[0].isupper()]
    imps  = [w for w in results if w not in props]
    return (props, imps)

def header(exp, props, imps, opts):
    indent = '  '
    extras = ''
    if '-g' in opts or '-c' in opts:
        theopts = []
        if '-g' in opts: theopts += ['global']
        if '-c' in opts: theopts += ['case-sensitive']
        extras = ", ".join(theopts) + " search"

    catstxt = ''
    if '-n' in opts and '-p' in opts:
        catstxt = 'searching the empty set'
    elif '-n' in opts:
        catstxt = 'excluding proper nouns'
    elif '-p' in opts:
        catstxt = 'proper nouns only'
    else:
        catstxt = k(props) + " proper ~ " + k(imps) + " common";

    h = "="*50 + "\n"
    h += indent + k(props+imps) + " results for /" + exp + "/" + "\n"
    h += indent*3 + catstxt + "\n"
    if extras: h += indent*3 + extras + "\n"
    h += "="*50 + "\n"
    return h

# because I'm lazy
def k(l): return str(len(l))

# to format the results
def wordcols(words, tab, ugly, mincolheight=9):
    wcount = len(words)

    if ugly:
        return ", ".join(words) + "\n"

    # return one column if there are just a few results
    if wcount < 2*mincolheight:
        return (" + "+"\n + ".join(words)+"\n") if wcount else None

    else:
        cols  = max( min( _terminalwidth//(tab+7), round(wcount/mincolheight) ), 1 ) # number of columns
        height = ceil(wcount/float(cols)) # column height

        cols = int(cols)
        height = int(height)

        words = words + [""]*((cols-(wcount-cols*height))%cols) # fill in the rest of the matrix with blanks

        wlist = []
        for i in range(height):
            r = ''
            for c in range(cols):
                word = words[i+c*height]
                if c != cols-1:
                    word = words[i+c*height].ljust(tab+5) # justify, but not column one
                if len(word.strip()) > 0:
                    r += " + " + word

            wlist += [r]

        return "\n".join(wlist) + "\n"

def usage():
    print(__doc__)

if __name__ == "__main__":
    main(sys.argv[1:])

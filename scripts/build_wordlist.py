#!/usr/bin/env python3
"""Build Lexitron's word list from the English Speller Database (SCOWL v2).

Usage:
    git clone -b v2 https://github.com/en-wl/wordlist.git
    (cd wordlist && make)                  # builds wordlist/scowl.db
    python3 scripts/build_wordlist.py wordlist/scowl.db

Writes lexitron/words.tsv.gz, one word per line, sorted from most to least
common (Lexitron stops reading once it passes the requested size):

    word <TAB> size <TAB> base size <TAB> base forms

- size: SCOWL size of the most common entry for the word (35 = core
  vocabulary ... 95 = very obscure).
- base size: size of the most common entry where the word is its own base
  form (e.g. "go" but not "went"), or "-" if it is only ever inflected.
- base forms: comma-separated base forms the word is an inflection of,
  other than itself (e.g. "went" -> "go").

All spellings (US, British, Canadian, Australian) are included. Left out:
possessives, abbreviations, prefixes and suffixes, Roman numerals, programmer
slang, letter names ("b", "x"), contraction endings ("'ll"), uncommon or
invalid variant spellings, and entries containing digits or dots. Accents are
removed ("café" -> "cafe").
"""

import argparse, gzip, re, sqlite3, subprocess, unicodedata
from collections import defaultdict
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent.parent / 'lexitron' / 'words.tsv.gz'

# Rows from SCOWL's main view, with each word's base form (lemma). legacy_level
# rates variant spellings: 0 = preferred ... 2 = acceptable, 3 = uncommon or
# archaic, 4 = invalid.
QUERY = """
    select s.word, l.lemma, s.size
      from scowl_ s join lemmas l using (lemma_id)
     where s.legacy_level <= 2
       and s.pos not in ('np', 'nsp', 'nssp', 'abbr', 'pre', 'suf')
       and coalesce(s.category, '') not in ('roman-numerals', 'hacker')
       -- Letter names ("b", "x") as nouns or adjectives; "a" and "I" survive
       -- through their other parts of speech
       and not (length(s.word) = 1 and s.pos in ('n0', 'ns', 'aj0'))
"""

# Letters, optionally joined by spaces, hyphens or apostrophes
VALID_WORD = re.compile(r"'?[A-Za-z]+(?:[-' ]+[A-Za-z]+)*'?")

# Endings SCOWL lists as words of their own
CONTRACTION_ENDINGS = {"'d", "'ll", "'m", "'re", "'s", "'t", "'ve"}


def deaccent(word):
    decomposed = unicodedata.normalize('NFKD', word)
    return ''.join(c for c in decomposed if not unicodedata.combining(c))


def scowl_version(db_path):
    """The git commit of the SCOWL checkout the database was built in."""
    try:
        return subprocess.run(['git', 'log', '-1', '--format=%h %ad', '--date=short'],
            cwd=Path(db_path).resolve().parent, capture_output=True,
            text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return 'unknown'


def main():
    parser = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('db', help='path to scowl.db')
    parser.add_argument('-o', '--output', type=Path, default=OUTPUT)
    args = parser.parse_args()

    size = {}
    base_size = {}
    base_forms = defaultdict(set)

    db = sqlite3.connect(args.db)
    for word, lemma, word_size in db.execute(QUERY):
        word, lemma = deaccent(word), deaccent(lemma)
        if not VALID_WORD.fullmatch(word) or word in CONTRACTION_ENDINGS:
            continue

        size[word] = min(word_size, size.get(word, word_size))
        if word == lemma:
            base_size[word] = min(word_size, base_size.get(word, word_size))
        else:
            base_forms[word].add(lemma)

    with gzip.open(args.output, 'wt', encoding='ascii', newline='\n') as f:
        f.write(f'# Built from SCOWL v2 (ESDB) commit {scowl_version(args.db)}; '
                'see scripts/build_wordlist.py\n')
        for word in sorted(size, key=lambda w: (size[w], w)):
            f.write('\t'.join([word, str(size[word]),
                               str(base_size.get(word, '-')),
                               ','.join(sorted(base_forms[word]))]) + '\n')

    print(f'Wrote {len(size)} words to {args.output}')


if __name__ == '__main__':
    main()

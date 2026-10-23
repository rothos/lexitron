#!/usr/bin/env python3
"""Build Lexitron's pronunciations, for ry, from the CMU Pronouncing Dictionary.

Usage:
    git clone https://github.com/cmusphinx/cmudict.git /tmp/cmudict
    uv run --python 3.11 --with g2p_en --with-editable . \\
        python scripts/build_pronunciations.py /tmp/cmudict

Writes lexitron/pronunciations.tsv.gz, one word per line, for every word in
the word list (lowercased, and each word of a phrase):

    word <TAB> source <TAB> pronunciations

- source: c if the CMU Pronouncing Dictionary has the word; d if it's
  derived from words it has, by lexitron.rhymes.derive ("chasms" from
  "chasm", "humanise" from "humanize", "sheepherder" from "sheep" and
  "herder"); g if it's guessed by g2p_en, a model trained on the
  dictionary, or derived from such a guess.
- pronunciations: space-separated, each encoded with one character per
  phoneme (see lexitron.rhymes.CODE).

Words are derived or guessed shortest first, so longer words can be derived
from shorter ones' guesses ("sonatinas" from "sonatina").
"""

import argparse, gzip, re, subprocess, sys
from pathlib import Path

from lexitron.lexitron import load_words
from lexitron.rhymes import CODE, derive, encode, tokens

OUTPUT = Path(__file__).resolve().parent.parent / 'lexitron' / 'pronunciations.tsv.gz'
# Stems and compound parts have to be words up to this SCOWL size, and
# three-letter compound parts up to the smaller one, so "secant" isn't taken
# for "sec" + "ant"
PART_LEVEL = 70
SHORT_PART_LEVEL = 50


def load_cmudict(path):
    """Map each word in cmudict.dict to its encoded pronunciations."""
    prons = {}
    for line in open(path, encoding='utf-8'):
        line = line.split('#')[0].strip()
        if not line:
            continue
        word, arpabet = line.split(' ', 1)
        word = re.sub(r'\(\d+\)$', '', word)
        try:
            pron = encode(arpabet)
        except KeyError:
            print(f"skipping {word}: {arpabet}", file=sys.stderr)
            continue
        if word.endswith(('ied', 'ies')) and pron[-2:-1] == CODE['IY2']:
            # "pitied" P IH1 T IY2 D: the ending isn't really stressed, and
            # would rhyme with "seed"
            pron = pron[:-2] + CODE['IY0'] + pron[-1]
        if pron.endswith(CODE['AH2']):
            # "gaga" G AA1 G AH2: likewise, and "gagas" would rhyme with "does"
            pron = pron[:-1] + CODE['AH0']
        prons.setdefault(word, [])
        if pron not in prons[word]:
            prons[word].append(pron)
    return {word: tuple(p) for word, p in prons.items()}


def commit(path):
    try:
        return subprocess.run(['git', 'log', '-1', '--format=%h %ad', '--date=short'],
                              cwd=path, capture_output=True, text=True,
                              check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return 'unknown version'


def main():
    parser = argparse.ArgumentParser(description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('cmudict', type=Path,
                        help='a checkout of github.com/cmusphinx/cmudict')
    args = parser.parse_args()

    try:
        from g2p_en import G2p
    except ImportError:
        sys.exit("needs g2p_en: run with uv run --with g2p_en (see --help)")
    g2p = G2p()

    cmu = load_cmudict(args.cmudict / 'cmudict.dict')
    entries = load_words(95)
    wanted = sorted({t for word, _, _, _ in entries for t in tokens(word)})
    parts = {word.lower() for word, size, _, _ in entries
             if size <= PART_LEVEL and ' ' not in word and '-' not in word}
    common = {word.lower() for word, size, _, _ in entries
              if size <= SHORT_PART_LEVEL}

    result = {w: cmu[w] for w in wanted if w in cmu}
    source = {w: 'c' for w in result}
    missing = sorted((w for w in wanted if w not in result),
                     key=lambda w: (len(w), w))
    print(f"{len(wanted)} words; {len(result)} in CMUdict; deriving or "
          f"guessing {len(missing)}", file=sys.stderr)

    for n, word in enumerate(missing):
        used_guess = []

        def lookup(w):
            found = result.get(w) or cmu.get(w)
            if found and source.get(w) == 'g':
                used_guess.append(w)
            return found

        found = derive(word, lookup, parts.__contains__, common.__contains__)
        if found:
            source[word] = 'g' if used_guess else 'd'
        else:
            letters = re.sub('[^a-z]', '', word)
            guess = [p for p in g2p.predict(letters) if p in CODE] if letters else []
            if not any(p[-1] in '012' for p in guess):
                print(f"no pronunciation for {word!r}", file=sys.stderr)
                continue
            found = (''.join(CODE[p] for p in guess),)
            source[word] = 'g'
        result[word] = found
        if n % 10000 == 0:
            print(f"  {n}/{len(missing)} {word}", file=sys.stderr)

    counts = {s: sum(1 for v in source.values() if v == s) for s in 'cdg'}
    print(f"CMUdict {counts['c']}, derived {counts['d']}, guessed {counts['g']}",
          file=sys.stderr)

    lines = [f"# Built from CMUdict {commit(args.cmudict)}; "
             "see scripts/build_pronunciations.py"]
    lines += [f"{w}\t{source[w]}\t{' '.join(result[w])}" for w in sorted(result)]
    with gzip.open(OUTPUT, 'wt', encoding='ascii', compresslevel=9) as f:
        f.write('\n'.join(lines) + '\n')
    print(f"wrote {OUTPUT}", file=sys.stderr)


if __name__ == '__main__':
    main()

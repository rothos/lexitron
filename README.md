Lexitron
==============================================================================

A command-line regex search engine for the English language.


Requirements
------------------------------------------------------------------------------
The only requirement is **Python** 3.9 or later.

If you try to install Lexitron and something goes wrong, let me know what your
system details are and I'll try to get it fixed.


Installation
------------------------------------------------------------------------------
Lexitron is available on the Python Package Index (pip). To install, simply
type
```
$ pip install lexitron
```
at the command line.

Once the install is complete, you can access Lexitron with the `lx` command at
the terminal.


Quick tour
------------------------------------------------------------------------------
- `lx '.*icide'`: words ending in "icide"
- `lx -s rdb`: words containing "rdb" anywhere
- `lx 'b.a.k'`: five-letter words matching B?A?K
- `lx -a listen`: anagrams of "listen"
- `lx -f aeilnrst`: words you can spell from these letters
- `lx -f abcdef.`: the same, with a blank tile
- `lx -l 4- -rf eihnglw -s h`: today's Spelling Bee (center letter "h")
- `lx -i q -e u`: words with a "q" but no "u"
- `lx -t a.a.a`: words shaped like "rarer"
- `lx -w crane:..y.g`: Wordle candidates
- `lx --hooks cat`: Scrabble hooks for "cat"
- `lx -n '.*tion'`: how many words end in "tion"

More in [Examples](#examples).


Usage
------------------------------------------------------------------------------
Usage syntax is

```
$ lx [options] [expression]
$ lx -f|-a [options] letters [expression]
```

where `expression` is a regular expression and `[options]` are as follows.
The expression can be left out when another option says what to look for
(`lx -t abba`, `lx -w crane:..y.g`).

The expression must match the **whole word**, so `lx cat` finds only "cat",
and `lx ".*cat"` finds words ending in "cat". To match the expression anywhere
within a word, use `-s` (so `lx -s cat` finds "cat", "catalog", "bobcat",
etc).

Inflected forms (plurals, conjugations, etc, like "went" or "oxen") are
searched along with base forms. Use `-b` to search base forms only. Phrases
with spaces are listed in their base form only ("sperm whale", not "sperm
whales").

Searches are case-insensitive unless you use `-c`. Options can go before or
after the expression. Quote the expression (`'...'`) so your shell doesn't
interpret characters like `*`, `?` and `$`.

**zsh tip:** add `alias lx='noglob lx'` to your `~/.zshrc` and you can skip
the quotes for `*` and `?`: `lx .*icide`, `lx colou?r`.

### A little regex

 pattern       | matches
---------------|---------------------------------------------------------------
 `.`           | any one character: `b.a.k` is B?A?K
 `.*`          | anything, including nothing: `.*cake`, `un.*able`
 `[aeiou]`     | one of these letters
 `[^aeiou]`    | any letter except these
 `x+`, `x?`    | one or more x; zero or one x: `colou?r`
 `x{3}`, `x{2,4}` | exactly 3 x; 2 to 4 x
 `a\|b`        | a or b: `cat\|dog`
 `(...)\1`     | a group, then the same text again: `(...)\1` is "murmur"
 `(?=.*e)`     | lookahead: "the word contains an e"

### Expressions, letters and patterns

The same characters mean different things in different places:

- In the **expression**, they're regex: `lx 'dot?'` finds "do" and "dot"
  (`?` makes the "t" optional).
- In **letters** (`-f`, `-a`), each letter is a tile and `.` is a blank:
  `lx -a dot.` finds "dote", "doth", "toad" and so on.
- In a **pattern** (`-t`), each letter is a placeholder: `lx -t abba` finds
  "deed", "noon" and so on.

### How the expression matches

 option          | function
-----------------|-------------------------------------------------------------
 `-s`            | Match anywhere within a word, rather than the whole word
 `-c`            | Case-sensitive search

### Spelling from letters

 option          | function
-----------------|-------------------------------------------------------------
 `-f`            | Only words spelled from the given letters, each used at most as often as given; `.` is a blank
 `-a`            | Only anagrams: words that use exactly the given letters
 `-r`            | With `-f` or `-a`, letters may be used any number of times

With `-f` and `-a`, the letters come first, optionally followed by an
expression: `lx -a aerst` finds all anagrams of "aerst", `lx -a aerst 's.*'`
only the ones starting with "s". Lengths and letters count letters only,
ignoring apostrophes, hyphens and spaces.

In the letters, `.` is a blank tile that can stand for any one letter:
`lx -f abcdef.`. With `-a`, blanks must be used, like the rest of the
letters.

### More filters

 option          | function
-----------------|-------------------------------------------------------------
 `-l N`          | Only words with this many letters: `5`, `4-7`, `5-` (5 or more) or `-7` (up to 7)
 `-i LETTERS`    | Only words containing all of these letters; repeats count, so `ee` means at least two e's
 `-e LETTERS`    | Only words containing none of these letters
 `-t PATTERN`    | Only words with this shape (see below)

In a pattern, each letter stands for some letter: the same letter for the same
letter, different letters for different ones. `.` is any letter, and as in
regex, `.*` is any run of letters (`.+` one or more, `.?` zero or one). So
`abba` matches "deed" but not "dddd", `a.a.a` matches "rarer", and `ab.*ab`
matches words that start and end with the same two letters, like "enlighten".
The pattern only describes shape; to fix actual letters, add an expression:
`lx -t a.a.a 'r.*'`.

### Word games

 option          | function
-----------------|-------------------------------------------------------------
 `-w GUESS:RESULT` | Wordle: the guess, a colon, then `g` (green), `y` (yellow) or `.` (grey) for each letter; repeat for each guess
 `--probes`      | With `-w`, list only guesses that can't be the answer: the 20 best, then the 20 worst
 `--plus WORD`   | Words made by inserting one letter anywhere: cat → cart, chat
 `--minus WORD`  | Words made by removing one letter: cart → art, car, cat
 `--change WORD` | Words made by changing one letter, as in word ladders: cat → bat, cot
 `--hooks WORD`  | Scrabble hooks: letters that go on the front or back of the word

`-w` sets the length from the guess, and uses level 50 unless you give `-L`,
since Wordle answers are everyday words. A repeated letter is handled the way
Wordle does it: in `geese:.y...`, the grey second and third "e" mean the word
has exactly one "e".

With `-w`, the best guesses come first (`-o best`), each with its score: how
evenly its colors would split the remaining candidates, as expected
information in bits. A higher score means fewer candidates left, on average.

Sometimes a word that *can't* be the answer would narrow things down more,
for example by trying five new letters rather than repeating a green one. In
a terminal, up to 10 of these come first when they beat every candidate,
dimmed (or marked `*` when `NO_COLOR` is set). On a tie the candidate wins,
since it might be right. Piped output lists only the candidates. Use
`--probes` to see only these words: the 20 best and, after a `...` row, the
20 worst.

`--plus`, `--minus` and `--change` take an optional count, `cat:2` for two
letters. These and `--hooks` skip words with apostrophes. In a terminal,
`--hooks` shows the front hooks, the word and the back hooks; with `-x` or
when piped, it lists the hooked words.

### Which words to search

 option          | function
-----------------|-------------------------------------------------------------
 `-L N`          | Include words up to this obscurity level (see [Word list](#word-list)); default 70
 `-b`            | Search only base forms, not inflected forms like plurals and conjugations
 `-p`            | Include phrases and hyphenated entries, like "sperm whale"
 `-P`            | Search only phrases and hyphenated entries
 `-u`            | Include uppercase/proper words (like "France") in addition to lowercase/common words
 `-U`            | Search only for uppercase/proper words

### Output

 option          | function
-----------------|-------------------------------------------------------------
 `-o ORDER`      | Sort by `family` (the default; see [Output](#output)), `alpha`, `length` (shortest first), `common` (most common first) or `best` (best Wordle guess first; the default with `-w`)
 `-n`            | Print only the number of matches
 `-I`            | Print a header describing the search
 `-x`            | Print unformatted output, one word per line
 `-h`            | Print help and exit
 `-v`            | Print version and exit

Type `$ lx -h` for full help text.

If you aren't familiar with regular expressions, it isn't too hard to learn
the basics. There are many resources online. A good starting point is
the [Wikipedia article](https://en.wikipedia.org/wiki/Regular_expression).


Output
------------------------------------------------------------------------------
By default, Lexitron will output a well-formatted (potentially multi-column)
list of words. Use `-I` to add a header describing the results.

Words are sorted alphabetically, except that inflected forms (plurals,
conjugations and so on) come right after their base form when it's also in
the results: "run ran running runs runabout". In a terminal, the inflected
forms are dimmed, so each family stands out, and the other words are colored
by how common they are: bold green for core vocabulary, then green, yellow
and orange, to red for the most obscure (see [Word list](#word-list)).
`-o alpha` sorts strictly alphabetically, with the same styling. Set
`NO_COLOR` in your environment to turn styling off.

The results are separated into "proper" words (containing capitals, like
"France" or "USA") and "common" words (lowercase, like "boat").

Using the `-x` flag will return a more machine-readable output with one word
per line. This is also what you get automatically when the output isn't a
terminal (e.g. when piping into another command or redirecting to a file).
In that case the `-I` header goes to stderr, so it doesn't get mixed in with
the words.


Word list
------------------------------------------------------------------------------
Lexitron's dictionary comes from the English Speller Database (SCOWL), which
grades every word by how well known it is:

 level | roughly                                     | lowercase words
-------|---------------------------------------------|--------------
  35   | core vocabulary                             |  41,000
  50   | words in a small dictionary                 |  65,000
  60   | a standard dictionary (what spellcheckers use) |  84,000
  70   | a large dictionary (the default)            | 134,000
  80   | obscure words                               | 198,000
  95   | everything                                  | 253,000

All spellings are included: American, British, Canadian and Australian
("color" and "colour", "organize" and "organise"). Accents are removed
("café" becomes "cafe"). Possessives, abbreviations and Roman numerals are
left out.


Examples
------------------------------------------------------------------------------

### Word games

**NYT Spelling Bee.** Words of 4 or more letters, using only the seven
letters (each as often as you like), that contain the center letter "h"
(`-s h`). Spelling Bee doesn't accept contractions like "he'll".
```
$ lx -I -l 4- -rf eihnglw -s h
38 matches for /h/ from 'eihnglw' length 4-

ghee         high         wheelie
ghillie      hill         wheen
he'll        hinge        when
heel         hinging      whew
heeling      neigh        while
heinie       neighing     whiling
hell         nigh         whin
henge        nihil        whine
hewing       weigh        whining
hewn         weighing     whinge
hieing       whee         whingeing
higgle       wheel        whinging
higgling     wheeling
```

**Spelling Bee pangrams.** `-ra` finds words that use every one of the
letters, each as often as you like.
```
$ lx -ra eihnglw
wheeling
```

**Wordle.** One `-w` per guess: `g` for green, `y` for yellow, `.` for grey.
The best next guesses come first, with how much each would tell you, in bits.
The starred words can't be the answer, but would narrow things down more than
any word that could.
```
$ lx -w crane:.g...
pouts 4.88*    trims 4.19     drugs 3.74     frisk 3.36     brood 3.06
plots 4.82*    profs 4.14     troop 3.73     trout 3.33     groom 3.04
typos 4.78*    prism 4.14     proud 3.72     prior 3.30     brusk 3.00
posit 4.76*    frost 4.13     drift 3.69     proof 3.29     wroth 2.90
moist 4.70*    proms 4.10     group 3.67     brisk 3.28     privy 2.87
omits 4.70*    dript 4.09     trust 3.64     promo 3.21     troth 2.86
plods 4.68*    prows 4.08     trump 3.64     growl 3.19     drill 2.86
pilot 4.67*    gript 4.08     drums 3.62     drily 3.18     broom 2.86
tipsy 4.62*    writs 3.97     fruit 3.61     drool 3.17     grill 2.84
foist 4.60*    prosy 3.96     orbit 3.56     frump 3.17     droll 2.83
trips 4.48     grids 3.95     grubs 3.54     brush 3.17     proxy 2.82
trios 4.41     wrist 3.95     brows 3.53     troll 3.15     druid 2.79
prods 4.33     tromp 3.87     drubs 3.53     grimy 3.15     frill 2.67
prigs 4.30     brigs 3.86     droop 3.51     froth 3.14     truth 2.60
drops 4.30     frogs 3.82     truss 3.51     truly 3.13     brook 2.43
drips 4.27     trots 3.79     dross 3.48     trill 3.12     gruff 2.43
grits 4.25     props 3.75     prowl 3.44     broil 3.11     dryly 2.17
grist 4.22     grows 3.74     gross 3.43     broth 3.07     frizz 1.91
grips 4.20     brims 3.74     tryst 3.40     primp 3.07     wryly 1.78
```
After a second guess, the best you can do is a guess that might be right:
```
$ lx -w crane:..y.g -w toils:.y...
abode 2.00
above 2.00
adobe 2.00
awoke 0.81
```

**Wordle, by hand.** The same kind of search as a regex: "r" is second and
"n" is fourth, there's an "e" somewhere, and "o", "s" and "t" are out.
`(?=.*e)` is a lookahead: "contains an e".
```
$ lx '(?=.*e)[^ost]r[^ost]n[^ost]'
arena
brine
crane
crine
frena
prune
urine
```

**Scrabble hooks.** Letters that make a word when put in front of "at", and
after it.
```
$ lx --hooks at
bcefghklmoprstvw  at  e
```

**Q without U.**
```
$ lx -i q -e u
faqir        qindarka
faqirs       qindarkas
niqab        qintar
qadi         qintars
qadis        qoph
qi           qophs
qibla        qwerty
qiblas       sheqalim
qiblah       sheqel
```

**Word ladders.** Every word one letter away from "love".
```
$ lx --change love
cove
dove
hove
lave
live
lobe
lode
loge
lone
lope
lore
lose
move
rove
wove
```

**Adding a letter.**
```
$ lx --plus cat
cant
cart
cast
cate
cats
chat
coat
scat
```

**Crossword fill.** Five letters, B?A?K, most common first.
```
$ lx -o common 'b.a.k'
black
blank
```

**Scrabble bingos.** Every anagram of a rack.
```
$ lx -a retains
antsier
nastier
retains
retinas
retsina
stainer
stearin
```

**Words from a rack.** Five-letter words from "aeilnrst", most common first.
```
$ lx -o common -l 5 -f aeilnrst | head
aisle
alert
alien
aline
alter
aren't
arise
earls
earns
inert
```

**Blank tiles.** `.` stands for any one letter. Six-letter words or longer
from "abcdef" plus a blank:
```
$ lx -l 6- -f abcdef.
abduce
bached
backed
barfed
braced
cabbed
cabled
chafed
decaff
decafs
deface
fabled
facade
```
and the anagrams that use every tile:
```
$ lx -a zebr.
braze
zebra
```

### Exploring English

**Words ending in "icide".**
```
$ lx ".*icide"
aborticide      herbicide       patricide
acaricide       homicide        pesticide
algicide        infanticide     regicide
bactericide     insecticide     rodenticide
deicide         larvicide       sororicide
feticide        liberticide     spermicide
filicide        matricide       suicide
foeticide       menticide       tyrannicide
fratricide      miticide        uxoricide
fungicide       parasiticide    vaticide
germicide       parricide       vermicide
```

**Words containing "rdb"**, with the info header.
```
$ lx -Is rdb
18 matches for /rdb/

birdbath       hardbitten
birdbaths      hardboard
birdbrain      hardbound
birdbrains     swordbill
birdbrained    swordbills
cardboard      wordbook
hardback       wordbooks
hardbacks      yardbird
hardball       yardbirds
```

**Words shaped like "rarer"**: the same letter first, third and last.
```
$ lx -t a.a.a
abaca
abaya
afara
agama
asana
duded
ninon
ovolo
popup
rarer
sises
```

**Seven-letter palindromes** with four different letters, mirrored.
```
$ lx -t abcdcba
deified
racecar
reviver
rotator
```

**No vowels**, six letters or more.
```
$ lx -e aeiou -l 6-
crwths     rhythms
crypts     spryly
flybys     sylphs
ghylls     synchs
glyphs     synths
nymphs     syzygy
psychs     trysts
rhythm     tsktsk
```

**All five vowels, in order.**
```
$ lx '[^aeiou]*a[^aeiou]*e[^aeiou]*i[^aeiou]*o[^aeiou]*u[^aeiou]*'
abstemious
abstemiously
arsenious
facetious
facetiously
```

**The longest words you can type on the top row of a keyboard.**
```
$ lx -o length '[qwertyuiop]+' | tail -3
proprietor
repertoire
typewriter
```

**How many words end in "tion"?**
```
$ lx -n ".*tion"
2299
```
(Take this with a grain of salt: it depends on what you count as a word, and
which technical or niche jargons are included. Try `-L 95` to include obscure
words.)

**Words ending in "woman" versus words ending in "man" but not "woman".**
`(?<!wo)` is a lookbehind: "not preceded by wo".
```
$ lx -n ".*woman"
72
```
```
$ lx -n '.*(?<!wo)man'
323
```

**The same double letter twice**, except vowels and "s" (to skip
"-lessness"), including proper words. `\1` repeats whatever `(...)` matched,
and `-b` leaves out plurals like "hillbillies".
```
$ lx -Ibus "([^aeious])\1.*\1\1"
50 matches for /([^aeious])\1.*\1\1/ (8 proper, 42 common)

Allhallowmas
Allhallows
Allhallowtide
Boccaccio
Chancellorsville
Connellsville
Llewellyn
Ulladulla

acciaccatura        hullaballoo         pralltriller
allegorically       idyllically         razzamatazz
allergically        illegally           razzmatazz
ballistically       illiberally         riffraff
bellpull            illogically         rollerball
chiffchaff          intellectually      scuttlebutt
collaterally        jellyroll           skillfully
colloquially        kinnikinnick        syllabically
dillydally          metallically        syllogistically
dullsville          millennially        unskillfully
elliptically        monosyllabically    villanelle
flibbertigibbet     pellmell            volleyball
granddaddy          phallically         whippersnapper
hillbilly           pizzazz             willfully
```

**Acronyms of five or more letters**: proper words only (`-U`), in capitals
(`-c`).
```
$ lx -Uc '[A-Z]{5,}' | head
ALGOL
ANZUS
ASCII
ASEAN
ASPCA
AWACS
BAFTA
BASIC
BOGOF
CAPTCHA
```

**Phrases and compounds ending in "cake".**
```
$ lx -p ".*cake" | head
angel cake
angel food cake
beefcake
buckwheat cake
cake
cheesecake
coffee cake
coffeecake
cotton cake
cupcake
```

**Only phrases.** `-P` leaves out single words.
```
$ lx -P 'sperm.*'
sperm bank
sperm cell
sperm oil
sperm whale
spermatic cord
```


Using Lexitron from Python
------------------------------------------------------------------------------
```python
>>> from lexitron import search
>>> search('.*icide', sort='common')['common'][:3]
['fungicide', 'germicide', 'homicide']
```

`search()` takes the same options as the command line; see its docstring.


Changes in version 4.0
------------------------------------------------------------------------------
- New filters: `-i` (must contain these letters), `-e` (must not contain
  them) and `-t` (pattern: `abba` matches "deed", `a.a.a` matches "rarer").
- New word-game options: `-w` for Wordle (sorted best guess first), `--plus`, `--minus` and `--change`
  for adding, removing and changing letters, and `--hooks` for Scrabble
  hooks.
- New sort order `-o best`: best Wordle guess first. In a terminal, `-w`
  shows the bits of information each guess would give, with better guesses
  that can't be the answer first; `--probes` lists only those.
- **`-i` now means `--include`.** The info header is `-I`.
- **Blank tiles in `-f` and `-a` letters are `.` only**, matching `.` in
  expressions and patterns; `?` is no longer accepted.
- The expression can be left out when another option says what to search
  for.
- Shorter help, with options in a more sensible order, and a note on what
  `.` means in expressions, letters and patterns.
- The old option names `--only-phrases` and `--only-uppercase` are gone.


Changes in version 3.3.1
------------------------------------------------------------------------------
- Long option names are consistent: `--only-phrases` and `--only-uppercase`
  are now `--phrases-only` and `--uppercase-only`, like `--base-only` and
  `--number-only`. The old names still work.


Changes in version 3.3
------------------------------------------------------------------------------
- Phrases with spaces are listed in their base form only: "sperm whale" but
  not "sperm whales". SCOWL lists inflected forms for only a few phrases, so
  they're left out for consistency. Hyphenated words keep theirs ("x-rayed").


Changes in version 3.2
------------------------------------------------------------------------------
- New option `-P` searches only phrases and hyphenated entries, like
  "sperm whale"; `-p` still adds them to the usual results.


Changes in version 3.1
------------------------------------------------------------------------------
- New default sort, `family`: alphabetical, with inflected forms right after
  their base form ("run ran running runs"). `-o alpha` gives the old order.
- Terminal output is styled: inflected forms listed under their base form
  are dimmed, and other words are colored by how common they are, from bold
  green to red. Set `NO_COLOR` to turn this off; piped output is never
  styled.


Changes in version 3.0
------------------------------------------------------------------------------
- New word list: SCOWL replaces AGID, adding everyday words AGID was missing
  ("a", "of", "from"), British and other spellings, and obscurity levels
  (`-L`). The default level leaves out very obscure words; use `-L 95` to
  search everything.
- Expressions now match the whole word by default. In 2.x, `lx cat` matched
  any word containing "cat"; to get that behavior now, use `lx -s cat`.
- Inflected forms (plurals, conjugations, etc) are now searched too; use
  `-b` to search base forms only, as in 2.x.
- New options: letters (`-f`, `-a`, `-r`, with blank tiles), length
  (`-l`), sorting (`-o`), phrases (`-p`) and case-sensitive search (`-c`).
- Options can go anywhere on the command line.
- Output no longer crashes when piped or redirected; it falls back to one
  word per line.
- `-i` with `-n` prints the header line; `-u` and `-U` can no longer be
  combined.
- Invalid regular expressions give a short error message instead of a
  traceback.
- Quotation marks in the expression are no longer stripped, so you can
  search for words containing apostrophes.
- Lexitron can be used as a Python library.
- Requires Python 3.9 or later.


Acknowledgements
------------------------------------------------------------------------------
For its dictionary, Lexitron uses the English Speller Database (ESDB,
previously known as SCOWL) by Kevin Atkinson. See
[wordlist.aspell.net](http://wordlist.aspell.net/) and
`lexitron/SCOWL-Copyright.txt` for its copyright and license.

Versions before 3.0 used the Automatically Generated Inflection Database
(AGID), also by Kevin Atkinson.


License
------------------------------------------------------------------------------
Lexitron is licensed under GNU GPL Version 2.


Contact
------------------------------------------------------------------------------
Questions, bug reports, and feature requests can be filed on the [Github
issues tracker](//github.com/rothos/lexitron/issues).

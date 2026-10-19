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
- `lx -l 4- -rf eihnglw '.*h.*'`: today's Spelling Bee (center letter "h")
- `lx -n '.*tion'`: how many words end in "tion"

More in [Examples](#examples).


Usage
------------------------------------------------------------------------------
Usage syntax is

```
$ lx [options] expression
$ lx -f|-a [options] letters [expression]
```

where `expression` is a regular expression and `[options]` are as follows.

The expression must match the **whole word**, so `lx cat` finds only "cat",
and `lx ".*cat"` finds words ending in "cat". To match the expression anywhere
within a word, use `-s` (so `lx -s cat` finds "cat", "catalog", "bobcat",
etc).

Inflected forms (plurals, conjugations, etc, like "went" or "oxen") are
searched along with base forms. Use `-b` to search base forms only.

Searches are case-insensitive unless you use `-c`. Options can go before or
after the expression. Quote the expression (`'...'`) so your shell doesn't
interpret characters like `*`, `?` and `$`.

**zsh tip:** add `alias lx='noglob lx'` to your `~/.zshrc` and you can skip
the quotes for `*` and `?`: `lx .*icide`, `lx -f abcdef?`.

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

### What to match

 option          | function
-----------------|-------------------------------------------------------------
 `-s`            | Match anywhere within a word, rather than the whole word
 `-c`            | Case-sensitive search
 `-l N`          | Only words with this many letters: `5`, `4-7`, `5-` (5 or more) or `-7` (up to 7)
 `-f`            | Only words spelled from the given letters, each used at most as often as given; `?` or `.` is a blank
 `-a`            | Only anagrams: words that use exactly the given letters
 `-r`            | With `-f` or `-a`, letters may be used any number of times

With `-f` and `-a`, the letters come first, optionally followed by an
expression: `lx -a aerst` finds all anagrams of "aerst", `lx -a aerst 's.*'`
only the ones starting with "s". Lengths and letters count letters only,
ignoring apostrophes, hyphens and spaces.

In the letters, `?` or `.` is a blank tile that can stand for any one letter:
`lx -f 'abcdef?'`. Quote it when using `?`, or your shell may treat it as a
filename wildcard (zsh says "no matches found"). `.` needs no quotes. With
`-a`, blanks must be used, like the rest of the letters.

### Which words to search

 option          | function
-----------------|-------------------------------------------------------------
 `-b`            | Search only base forms, not inflected forms like plurals and conjugations
 `-L N`          | Include words up to this obscurity level (see [Word list](#word-list)); default 70
 `-p`            | Include phrases and hyphenated entries, like "sperm whale"
 `-u`            | Include uppercase/proper words (like "France") in addition to lowercase/common words
 `-U`            | Search only for uppercase/proper words

### Output

 option          | function
-----------------|-------------------------------------------------------------
 `-i`            | Print info header along with search results
 `-n`            | Print only the number of matches
 `-o ORDER`      | Sort by `alpha` (the default), `length` (shortest first) or `common` (most common first)
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
list of words. Use `-i` to add a header describing the results.

The results are separated into "proper" words (containing capitals, like
"France" or "USA") and "common" words (lowercase, like "boat").

Using the `-x` flag will return a more machine-readable output with one word
per line. This is also what you get automatically when the output isn't a
terminal (e.g. when piping into another command or redirecting to a file).
In that case the `-i` header goes to stderr, so it doesn't get mixed in with
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
letters (each as often as you like), that contain the center letter "h".
`[a-z]` leaves out words with apostrophes, like "he'll".
```
$ lx -i -l 4- -rf eihnglw '[a-z]*h[a-z]*'
37 matches for /[a-z]*h[a-z]*/ from 'eihnglw'

ghee         hill         wheen
ghillie      hinge        when
heel         hinging      whew
heeling      neigh        while
heinie       neighing     whiling
hell         nigh         whin
henge        nihil        whine
hewing       weigh        whinge
hewn         weighing     whingeing
hieing       whee         whinging
higgle       wheel        whining
higgling     wheelie
high         wheeling
```

**Spelling Bee pangrams.** `-ra` finds words that use every one of the
letters, each as often as you like.
```
$ lx -ra eihnglw
wheeling
```

**Wordle.** "r" is second and "n" is fourth, there's an "e" somewhere, and
"o", "s" and "t" are out. `(?=.*e)` is a lookahead: "contains an e".
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

**Blank tiles.** `?` stands for any one letter. Six-letter words or longer
from "abcdef" plus a blank:
```
$ lx -l 6- -f 'abcdef?'
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
$ lx -a 'zebr?'
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
$ lx -is rdb
18 matches for /rdb/

birdbath       hardbitten
birdbaths      hardboard
birdbrain      hardbound
birdbrained    swordbill
birdbrains     swordbills
cardboard      wordbook
hardback       wordbooks
hardbacks      yardbird
hardball       yardbirds
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
$ lx -ibus "([^aeious])\1.*\1\1"
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


Using Lexitron from Python
------------------------------------------------------------------------------
```python
>>> from lexitron import search
>>> search('.*icide', sort='common')['common'][:3]
['fungicide', 'germicide', 'homicide']
```

`search()` takes the same options as the command line; see its docstring.


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
- New options: letters (`-f`, `-a`, `-r`), length (`-l`), sorting (`-o`),
  phrases (`-p`) and case-sensitive search (`-c`).
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

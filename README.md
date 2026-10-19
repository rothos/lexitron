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


Usage
------------------------------------------------------------------------------
Usage syntax is

```
$ lx [options] expression
```

where `expression` is a regular expression and `[options]` are as follows.

The expression must match the **whole word**, so `lx cat` finds only "cat",
and `lx ".*cat"` finds words ending in "cat". To match the expression anywhere
within a word, use `-s` (so `lx -s cat` finds "cat", "catalog", "bobcat",
etc).

Inflected forms (plurals, conjugations, etc, like "went" or "oxen") are
searched along with base forms. Use `-b` to search base forms only.

Searches are case-insensitive unless you use `-c`.

### What to match

 option          | function
-----------------|-------------------------------------------------------------
 `-s`            | Match anywhere within a word, rather than the whole word
 `-c`            | Case-sensitive search
 `-l N`          | Only words with this many letters: `5`, `4-7`, `5-` (5 or more) or `-7` (up to 7)
 `-f LETTERS`    | Only words spelled from these letters, each used at most as often as given
 `-a LETTERS`    | Only anagrams: words that use exactly these letters
 `-r`            | With `-f` or `-a`, letters may be used any number of times

The expression is optional with `-f` and `-a`. Lengths and letters count
letters only, ignoring apostrophes, hyphens and spaces.

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

 level | roughly                                     | common words
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

### Example 1
A list of English words ending with "icide".
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

### Example 2
A list of English words that contain the substring "rdb", printed with info
header.
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

### Example 3
The number of English words that end in "tion".
```
$ lx -n ".*tion"
2299
```
(This number should be taken with a grain of salt, since no dictionary
is perfect, and it depends on what you count as a valid english word,
and which technical or niche jargons are included; etc etc. Try it with
`-L 95` to include obscure words.)

### Example 4
Anagrams of "listen".
```
$ lx -a listen
enlist
inlets
listen
silent
tinsel
```

### Example 5
Five-letter words that can be made from the letters of "nastier" plus "l",
most common first.
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

### Example 6
Words made only from the letters n, i and o, using each as often as you like.
```
$ lx -r -f nio
'n'
in
inion
inn
ion
ninon
no
non
noon
o'
oi
on
onion
oo
```

### Example 7
A list of English words with the same double letter appearing twice, except
for those whose double letter is a vowel or the letter `s` (to ignore
words of the form `*lessness`), printed with info header. Only base forms
are searched, to leave out plurals like "hillbillies".
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

### Example 8
Compare the number of English words that end in "woman"
with the number that end in "man".
```
$ lx -n ".*woman"
72
```
```
$ lx -n '.*(?<!wo)man'
323
```

### Example 9
Phrases and compound words ending in "cake".
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

Lexitron
==============================================================================

A command-line regex search engine for the English language.


Requirements
------------------------------------------------------------------------------
The only major requirement is **Python**.

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

 option | function
--------|-------------------------------------------------
  `-b`  | Search only base forms, not inflected forms like plurals and conjugations
  `-c`  | Case-sensitive search
  `-h`  | Print help and exit
  `-i`  | Print info header along with search results
  `-n`  | Print only the number of matches
  `-s`  | Match anywhere within a word, rather than the whole word
  `-u`  | Include uppercase/proper words (like "France") in addition to lowercase/common words
  `-U`  | Search only for uppercase/proper words
  `-v`  | Print version and exit
  `-x`  | Print unformatted output, one word per line

Type `$ lx -h` for full help text.

If you aren't familiar with regular expressions, it isn't too hard to learn
the basics. There are many resources online. A good starting point is
the [Wikipedia article](https://en.wikipedia.org/wiki/Regular_expression).


Output
------------------------------------------------------------------------------
By default, Lexitron will output a well-formatted (potentially multi-column)
list of words. Use `-i` to add a header describing the results.

The results are separated into "proper" words (capitalized, like "France")
and "common" words (lowercase, like "boat").

Using the `-x` flag will return a more machine-readable output with one word
per line. This is also what you get automatically when the output isn't a
terminal (e.g. when piping into another command or redirecting to a file).
In that case the `-i` header goes to stderr, so it doesn't get mixed in with
the words.


Examples
------------------------------------------------------------------------------

### Example 1
A list of lowercase English words ending with "icide".
```
$ lx ".*icide"
aborticide      germicide       ovicide         spermicide
acaricide       giganticide     parasiticide    sporicide
agricide        herbicide       parasuicide     stillicide
algicide        homicide        parricide       suicide
aphicide        infanticide     patricide       tyrannicide
aphidicide      insecticide     pesticide       uxoricide
bacillicide     larvicide       prolicide       vaticide
bactericide     liberticide     pulicide        verbicide
deicide         matricide       raticide        vermicide
feticide        medicide        regicide        viricide
filicide        menticide       rodenticide     vulpicide
foeticide       miticide        scabicide
fratricide      molluscicide    silicide
fungicide       nematicide      sororicide
```

### Example 2
A list of lowercase English words that contain the substring "rdb", printed with info header.
```
$ lx -is rdb
37 matches for /rdb/

birdbath           hardbeams          standardbearers
birdbaths          hardboard          standardbred
birdbrain          hardboards         standardbreds
birdbrains         hardboot           swordbill
cardboard          hardboots          swordbills
cardboards         hardbound          thirdborough
hardback           herdbook           thirdboroughs
hardbacks          herdbooks          wordbook
hardbake           herdboy            wordbooks
hardbakes          herdboys           yardbird
hardball           leopardbane        yardbirds
hardballs          recordbook
hardbeam           standardbearer
```

### Example 3
The number of lowercase English words that end in "tion".
```
$ lx -n ".*tion"
3393
```
(This number should be taken with a grain of salt, since no dictionary
is perfect, and it depends on what you count as a valid english word,
and which technical or niche jargons are included; etc etc.)


### Example 4
A list of English words with the same double letter appearing twice, except
for those whose double letter is a vowel or the letter `s` (to ignore
words of the form `*lessness`), printed with info header. Only base forms
are searched, to leave out plurals like "hillbillies".
```
$ lx -ibus "([^aeious])\1.*\1\1"
45 matches for /([^aeious])\1.*\1\1/ (9 proper, 36 common)

Allhallowmas
Allhallows
Allhallowtide
Armillariella
Chancellorsville
Dullsville
Gallirallus
Hunnemannia
Llullaillaco

acciaccatura       jellyroll          rollcollar
bellpull           kinnikinnic        rollerball
chiffchaff         kinnikinnick       scuttlebutt
dillydallier       millefeuille       shillyshally
dillydally         niffnaff           skillfully
dullsville         parallelling       snippersnapper
flibbertigibbet    pellmell           villanelle
granddaddy         pizzazz            volleyball
hallalling         pralltriller       volleyballer
hillbilly          razzamatazz        whippersnapper
huggermugger       razzmatazz         willfully
hullaballoo        riffraff           yellowbelly
```

### Example 5
Compare the number of lowercase English words that end in "woman"
with the number that end in "man".
```
$ lx -n ".*woman"
92
```
```
$ lx -n '.*(?<!wo)man'
562
```


Changes in version 3.0
------------------------------------------------------------------------------
- Expressions now match the whole word by default. In 2.x, `lx cat` matched
  any word containing "cat"; to get that behavior now, use `lx -s cat`.
- Inflected forms (plurals, conjugations, etc) are now searched too; use
  `-b` to search base forms only, as in 2.x.
- New `-c` flag for case-sensitive searches.
- `-i` with `-n` prints the header line; `-u` and `-U` can no longer be
  combined.
- Output no longer crashes when piped or redirected; it falls back to one
  word per line.
- Invalid regular expressions give a short error message instead of a
  traceback.
- Quotation marks in the expression are no longer stripped, so you can
  search for words containing apostrophes.
- Requires Python 3.9 or later.


Acknowledgements
------------------------------------------------------------------------------
For its dictionary, Lexitron uses the Automatically Generated
Inflection Database (AGID) by Kevin Atkinson. See
[http://wordlist.sourceforge.net/]([http://wordlist.sourceforge.net/]).


License
------------------------------------------------------------------------------
Lexitron is licensed under GNU GPL Version 2.


Contact
------------------------------------------------------------------------------
Questions, bug reports, and feature requests can be filed on the [Github
issues tracker](//github.com/rothos/lexitron/issues).

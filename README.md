Lexitron
==============================================================================

A command-line regex search engine for the English language.


Requirements
------------------------------------------------------------------------------
The only major requirement is **Python**.

I don't actually know which versions of Python this package will work on, I've
only tested on my own system which is using Python 3.11. Any feedback about
what works and doesn't would be helpful.

I did not write Lexitron to work on Windows, although it is a simple enough
package that I don't see why it shouldn't.

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

 option | function
--------|-------------------------------------------------
  `-d`  | Append start and end delimiters `^...$` to search query
  `-n`  | Print only the number of matches
  `-u`  | Search only for lowercase/common/uncapitalized words
  `-U`  | Search only for uppercase/proper/capitalized words
  `-v`  | Show version and exit
  `-x`  | Print unformatted output, one word per line

Type `$ lx -h` for full help text.

If you aren't familiar with regular expressions, it isn't too hard to learn
the basics. There are many resources online. A good starting point is
the [Wikipedia article](https://en.wikipedia.org/wiki/Regular_expression).


Output
------------------------------------------------------------------------------
By default, Lexitron will output a well-formatted (potentially multi-column)
list of words, along with a header describing the results.

The results are separated into "proper" words (capitalized, like "France")
and "common" words (lowercase, like "boat").

Using the `-x` flag will return a more machine-readable output with one word
per line.


Examples
------------------------------------------------------------------------------

### Example 1
A list of English words ending with "icide".
```
$ lx icide$
---------------------------------------------------------------------------
53 results for /.*icide/
0 proper ~ 53 common
---------------------------------------------------------------------------

aborticide      foeticide       matricide       pesticide       stillicide
acaricide       fratricide      medicide        prolicide       suicide
agricide        fungicide       menticide       pulicide        tyrannicide
algicide        germicide       miticide        raticide        uxoricide
aphicide        giganticide     molluscicide    regicide        vaticide
aphidicide      herbicide       nematicide      rodenticide     verbicide
bacillicide     homicide        ovicide         scabicide       vermicide
bactericide     infanticide     parasiticide    silicide        viricide
deicide         insecticide     parasuicide     sororicide      vulpicide
feticide        larvicide       parricide       spermicide
filicide        liberticide     patricide       sporicide
```

### Example 2
A list of English words that contain the substring "rdb".
```
$ lx rdb
---------------------------------------------------------------------------
21 results for /rdb/
1 proper ~ 20 common
---------------------------------------------------------------------------

Standardbred

birdbath          herdbook
birdbrain         herdboy
cardboard         leopardbane
hardback          recordbook
hardbake          standardbearer
hardball          standardbred
hardbeam          swordbill
hardboard         thirdborough
hardboot          wordbook
hardbound         yardbird
```

### Example 3
The number of lowercase English words that end in "tion".
```
$ lx -nxu ".*tion"
3837
```
(This number should be taken with a grain of salt, since no dictionary
is perfect, and it depends on what you count as a valid english word,
and which technical or niche jargons are included; etc etc.)


### Example 4
A list of English words with the same double letter appearing twice, except
for those whose double letter is a vowel or the letter `s` (to ignore
words of the form `*lessness`).
```
$ lx "([^aeious])\1.*\1\1"
---------------------------------------------------------------------------
45 results for /([^aeious])\1.*\1\1/
9 proper ~ 36 common
---------------------------------------------------------------------------

Allhallowmas
Allhallows
Allhallowtide
Armillariella
Chancellorsville
Dullsville
Gallirallus
Hunnemannia
Llullaillaco

acciaccatura       hillbilly          pellmell           shillyshally
bellpull           huggermugger       pizzazz            skillfully
chiffchaff         hullaballoo        pralltriller       snippersnapper
dillydallier       jellyroll          razzamatazz        villanelle
dillydally         kinnikinnic        razzmatazz         volleyball
dullsville         kinnikinnick       riffraff           volleyballer
flibbertigibbet    millefeuille       rollcollar         whippersnapper
granddaddy         niffnaff           rollerball         willfully
hallalling         parallelling       scuttlebutt        yellowbelly
```

### Example 5
Compare the number of lowercase/uncapitalized words that end in "woman"
with the number that end in "man".
```
$ lx -nxu ".*woman"
107
```
```
$ lx -nxu ".*(?<\!wo)man"
1145
```


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
issues tracker](//github.com/hrothgar/lexitron/issues).

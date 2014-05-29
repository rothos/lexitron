Lexitron
==============================================================================

A regex search engine for the English language.


Requirements
------------------------------------------------------------------------------

The only major requirement is **Python**. It should work with other versions,
but I have only tested Lexitron with Python 2.7.

I did not write Lexitron to work on Windows, although it is a simple enough
package that I don't see why it shouldn't.

If you try to install Lexitron and something goes wrong, let me know what your
system details are and I'll try to get it fixed.


Installation and usage
------------------------------------------------------------------------------
After downloading, navigate inside Lexitron's folder, where you should find a
`setup.py` script. For Linux and OS X users, the install is as easy as
```
$ sudo python setup.py install
```
Once the install is complete, you can access Lexitron with the `lx` command at
the terminal.

## Usage

Usage is

```
$ lx [options] expression
```

where `expression` is a regular expression and `[options]` are as follows.

 option | function
--------|-------------------------------------------------
  `-a`  | Search only for common (non-capitalized) words
  `-A`  | Search only for proper (capitalized) words
  `-g`  | Global search; equivalent to  `.*expression.*`
  `-c`  | Case-sensitive search
  `-n`  | Print only the number of matches
  `-x`  | Print unformatted output

Type `$ lx -h` for full help text.

## Examples

It's safest to put the search expression in quotation marks so that the shell
doesn't try to expand wildcards. If the search expression is only
alphanumerics, then quotation marks are unnecessary (though they are still a
good habit!).

### Example 1
A list of English words ending with "icide".
```
$ lx ".*icide"
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
$ lx -g rdb
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
The number of English words that end in "tion".
```
$ lx -nx ".*tion"
3449
```

### Example 4
A list of English words with the same double letter appearing twice, except
for those whose double letter is a vowel or the letter `s` (since there so
many words of the form `*lessness`).
```
$ lx -g "([^aeious])\1.*\1\1"
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
Compare the number of common (i.e. non-capitalized) words that end in "woman"
with the number that end in "man".
```
$ lx -nxa ".*woman"
92
```
```
$ lx -nxa ".*(?<\!wo)man"
562
```


Acknowledgements
------------------------------------------------------------------------------
For its dictionary, Lexitron uses the fantastic Automatically Generated
Inflection Database (AGID) by Kevin Atkinson. See
[http://wordlist.sourceforge.net/](http://wordlist.sourceforge.net/).


License
------------------------------------------------------------------------------
Lexitron is licensed under GPL v2.

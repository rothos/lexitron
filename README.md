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
After downloading, navigate inside Lexitron's folder, where you should find an
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
   -a   | Search only for common (non-capitalized) words
   -A   | Search only for proper (capitalized) words
   -g   | Global search; equivalent to  .\*expression.\*
   -c   | Case-sensitive search
   -n   | Print only the number of matches
   -x   | Print unformatted output

Type `$ lx -h` for full help text.

## Examples

It's safest to put the search expression in quotation marks so that the shell
doesn't try to expand wildcards. If the search expression is only
alphanumerics, then quotation marks are unnecessary (though they are still a
good habit!).

### Example 1
A list of English words ending with "ctrix".
```
$ lx ".*ctrix"
---------------------------------------------------------------------
7 results for /.*ctrix/
0 proper ~ 7 common
---------------------------------------------------------------------

directrix
protectrix
rectrix
tectrix
tractrix
trisectrix
victrix
```

### Example 2
A list of English words that contain the substring "rdb".
```
$ lx -g rdb
---------------------------------------------------------------------
21 results for /rdb/
1 proper ~ 20 common
---------------------------------------------------------------------

Standardbred

hardbake          birdbrain
recordbook        herdbook
thirdborough      hardbeam
hardboot          hardback
hardbound         swordbill
leopardbane       hardboard
herdboy           cardboard
yardbird          hardball
birdbath          standardbearer
standardbred      wordbook
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
---------------------------------------------------------------------
45 results for /([^aeious])\1.*\1\1/
9 proper ~ 36 common
---------------------------------------------------------------------

Armillariella
Chancellorsville
Hunnemannia
Allhallows
Allhallowtide
Gallirallus
Dullsville
Llullaillaco
Allhallowmas

pizzazz            riffraff           kinnikinnick       chiffchaff
whippersnapper     granddaddy         bellpull           niffnaff
razzmatazz         dillydally         willfully          volleyball
hillbilly          parallelling       huggermugger       hullaballoo
millefeuille       rollcollar         acciaccatura       scuttlebutt
shillyshally       rollerball         skillfully         dullsville
yellowbelly        flibbertigibbet    pralltriller       pellmell
jellyroll          snippersnapper     dillydallier       hallalling
razzamatazz        villanelle         volleyballer       kinnikinnic
```

### Example 5
Compare the number of common (i.e. non-capitalized) words that end in "woman"
with the number that end in "man".
```
$ lx -na ".*woman"
---------------------------------------------------------------------
92 results for /.*woman/
(restricted search)
---------------------------------------------------------------------

$ lx -na ".*(?<\!wo)man"
---------------------------------------------------------------------
562 results for /.*(?<!wo)man/
(restricted search)
---------------------------------------------------------------------
```


Acknowledgements
------------------------------------------------------------------------------
For its dictionary, Lexitron uses the fantastic Automatically Generated
Inflection Database (AGID) by Kevin Atkinson. See
[http://wordlist.sourceforge.net/](http://wordlist.sourceforge.net/).


License
------------------------------------------------------------------------------
Lexitron is licensed under GPL v2.

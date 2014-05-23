Lexitron
==============================================================================

A regex search engine for the English language (or any other wordset you like).


Requirements
------------------------------------------------------------------------------
Lexitron requires Python. [Version?]


Usage
------------------------------------------------------------------------------
Use Lexitron at a terminal by typing
```
$ python ~/path/to/lexitron.py [options] [expression]
```
For easier access, I'd recommend something like
```
$ alias lx="python ~/path/to/lexitron.py"
$ lx [options] [expression]
```

## Options

option  | function
------------------
`-g`    | global search
`-n`    | only return number of matches
`-h`    | show the help text
`-c`    | case-sensitive search (default is case-insensitive)
`-d`    | debug mode
`-u`    | prints unformatted results (CSV) rather than formatted columns

## Examples

It's safest to put the search expression in quotation marks so that the shell
doesn't try to expand wildcards. If the search expression is only
alphanumerics, then quotation marks are unnecessary (though they are still a
good habit!).

```
$ lx "g.gg.*"
```

```
$ lx ".*ctrix"
```

```
$ lx -g rdb
```

```
$ lx -n ".*tion"
```

```
$ lx -n ".*woman"
$ lx -n "[^(wo)]*man"
```


License
------------------------------------------------------------------------------
Lexitron is licensed under GPL v2.

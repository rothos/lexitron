# TODO

Findings from an audit of v2.1.2 (October 2026). Items marked ~~struck~~ are
fixed in 3.0.0.

## Bugs

1. ~~**Crashes when stdout isn't a terminal.**~~ `os.get_terminal_size()` in
   `print_results` was called unconditionally, so `lx foo | grep ...`,
   `lx foo > file`, and even `lx -n foo | ...` died with `OSError`; `-x`
   threw `BrokenPipeError` under `| head`. *Fixed: falls back to one word per
   line when not a TTY, and exits quietly on a broken pipe.*
2. ~~**Only headwords are searched.**~~ Each AGID line is
   `run V: ran | run | running | runs`, but `parse_line` kept only the first
   token, so forms like "went", "ran", "aardvarks" were unfindable. *Fixed:
   new `-a` flag adds inflected forms (90,949 → 203,658 common words). Forms
   AGID marks as questionable or generated (`? ! ~ <`) are left out.*
3. ~~**`sanitize` mangled input.**~~ It stripped one leading and one trailing
   `'` or `"` unconditionally, so `lx "a'"` silently searched for `a`, and
   `lx "'"` / `lx ''` crashed with `IndexError`. *Fixed: removed; the shell
   already strips quotes.*
4. ~~**Invalid regex printed a raw traceback**~~ (`lx '('`). *Fixed: argparse
   error message, exit status 2.*
5. ~~**Expressions starting with `-` are parsed as flags.**~~ *Not a real
   problem: no word in either list contains a hyphen, so such an expression
   can never match anything. `lx -- -foo` works if it ever matters.*
6. ~~**`ZeroDivisionError` when the terminal reports 0 rows**~~ (`formatted`,
   `N/(termheight/2.)`), under `script` and some embedded terminals. *Fixed
   as a side effect of switching to `shutil.get_terminal_size`, which falls
   back to 80x24.*
7. ~~**`requires-python = ">=3.7"` was wrong**~~: `importlib.resources.files`
   is 3.9+, and the backport was only installed for <3.8, so 3.8 broke.
   *Fixed: now `>=3.9`, backport dependencies dropped.*

## Word list

The dictionary needs improving; this is its own project.

- **Some very common words are missing.** AGID is an inflection database, so
  some words with no inflections never got an entry: "a", "of" and "from"
  are all absent, so `lx a` returns nothing.
- Lots of obscure entries ("aasvogel") with nothing to tell them apart from
  everyday words; no frequency/commonness data.
- AGID itself is old (wordlist.sourceforge.net); worth checking whether
  there's a newer release or a better source (e.g. SCOWL, which AGID is
  built from, has size/commonness levels).
- `agid-common.txt` has CRLF line endings, `agid-proper.txt` has LF.

## README

- ~~Examples 3 and 5 described unanchored searches as "ends in"~~. Correct
  now that matching is whole-word by default; counts and the stray backslash
  in `(?<\!wo)` are fixed.

## Rough edges

- `-i` is silently ignored with `-n` or `-x`; `-u -U` silently acts like `-U`.
- Header grammar: "1 matches".
- Always case-insensitive, no option to turn it off (`^DB$` returns both "dB"
  and "db").
- `LexitronParseError` / `_iter_words` silently skip unparseable lines.
- No tests, no CI.

## Ideas

- With `-a`, an option to show which headword a form came from.
- Crossword-style wildcards (`?` = one letter), length filters, sorting by
  length or commonness.

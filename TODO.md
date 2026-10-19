# TODO

Findings from an audit of v2.1.2 (October 2026). Items marked ~~struck~~ are
fixed in 3.0.0.

## Bugs

1. ~~**Crashes when stdout isn't a terminal.**~~ `os.get_terminal_size()` in
   `print_results` was called unconditionally, so `lx foo | grep ...`,
   `lx foo > file`, and even `lx -n foo | ...` died with `OSError`; `-x`
   threw `BrokenPipeError` under `| head`. *Fixed: falls back to one word per
   line when not a TTY, and exits quietly on a broken pipe.*
2. **Only headwords are searched.** Each AGID line is
   `run V: ran | run | running | runs`, but `parse_line` keeps only the first
   token. Forms like "went", "ran", "aahed", "aardvarks" are unfindable:
   ~111,600 inflected spellings that never appear as a headword, versus 90,949
   headwords searched.
3. **`sanitize` mangles input.** It strips one leading and one trailing `'` or
   `"` unconditionally:
   - `lx "a'"` silently searches for `a` (can't search for words ending in an
     apostrophe, e.g. `o'`)
   - `lx "'"` and `lx ''` crash with `IndexError`
4. **Invalid regex prints a raw traceback** (`lx '('`) instead of a clean
   error message and nonzero exit.
5. **Expressions starting with `-` are parsed as flags** (`lx -ism$`). Needs
   `lx -- -ism$`; not documented.
6. ~~**`ZeroDivisionError` when the terminal reports 0 rows**~~ (`formatted`,
   `N/(termheight/2.)`), under `script` and some embedded terminals. *Fixed
   as a side effect of switching to `shutil.get_terminal_size`, which falls
   back to 80x24.*
7. **`requires-python = ">=3.7"` is wrong.** `importlib.resources.files` is
   3.9+, and the backport is only installed for <3.8, so 3.8 breaks.
8. **Some very common words are missing from the dictionary.** AGID is an
   inflection database, so some words with no inflections never got an
   entry: "a", "of" and "from" are all absent, so `lx a` returns nothing.
   Needs a supplementary word list.

## README

- ~~Examples 3 and 5 described unanchored searches as "ends in"~~. Correct
  now that matching is whole-word by default; counts and the stray backslash
  in `(?<\!wo)` are fixed.

## Rough edges

- `-i` is silently ignored with `-n` or `-x`; `-u -U` silently acts like `-U`.
- Header grammar: "1 matches".
- Always case-insensitive, no option to turn it off (`^DB$` returns both "dB"
  and "db").
- `agid-common.txt` has CRLF line endings, `agid-proper.txt` has LF.
- AGID markers (`~ < ! ? {}`, variant-level digits) are ignored. They'll need
  handling once inflections are searched (~21k forms are flagged).
- No word frequency/commonness data, so obscure entries rank the same as
  common ones.
- `LexitronParseError` / `_iter_words` silently skip unparseable lines.
- No tests, no CI.

## Ideas

- Auto-switch to one-word-per-line when stdout isn't a TTY.
- Search inflections, with an option to show which headword a form came from.
- Crossword-style wildcards (`?` = one letter), length filters, a
  case-sensitive mode, sorting by length or commonness.

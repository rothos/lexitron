# TODO

## Ideas

- **Other word lists**, chosen with a flag or a config setting. The data
  format (`word, size, base size, base forms`) isn't SCOWL-specific, so other
  sources (ENABLE, Wiktionary, a hand-picked list) could be built into the
  same shape.
- **Show base forms**: the word list already records what each inflected
  form comes from ("went" → "go"); an option could print it.

## Done in 3.0.0

Audit of v2.1.2 (October 2026), all fixed:

- Crashed when output wasn't a terminal (`os.get_terminal_size`), and on
  broken pipes.
- Only AGID headwords were searched; inflected forms were unfindable.
- `sanitize()` stripped apostrophes and crashed on `''` and `"'"`.
- Invalid regexes printed tracebacks.
- `ZeroDivisionError` when the terminal reported 0 rows.
- `requires-python` claimed 3.7 but needed 3.9.
- README examples described unanchored searches as "ends in".
- Flags silently ignored in combination (`-i -n`, `-u -U`); "1 matches";
  no case-sensitive option; parse errors silently skipped; no tests or CI.
- Word list: AGID was missing everyday words ("a", "of", "from"), had no
  commonness data, and is no longer maintained. Replaced with SCOWL v2.

Not a bug after all: expressions starting with `-` are read as flags, but
no word contains a hyphen at the start, so they could never match anyway
(`lx -- -foo` works if needed).

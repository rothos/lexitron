# Releasing

## One-time setup

PyPI publishing uses [trusted publishing](https://docs.pypi.org/trusted-publishers/),
so there's no API token to manage.

1. On PyPI, go to the Lexitron project → Settings → Publishing → Add a new
   publisher (GitHub), with:
   - Owner: `rothos`
   - Repository: `lexitron`
   - Workflow: `release.yml`
   - Environment: `pypi`
2. On GitHub, go to the repo → Settings → Environments → New environment,
   named `pypi`. Optionally add yourself as a required reviewer, so each
   release waits for a click before publishing.

## Each release

1. Bump `version` in `pyproject.toml` and commit.
2. Tag and push:

   ```sh
   git tag v3.0.0
   git push origin master v3.0.0
   ```

The `release` workflow checks the tag matches the version, builds the
package, runs the tests against the built wheel, and publishes to PyPI.

## Updating the word list

The word list is built from the English Speller Database (SCOWL v2):

```sh
git clone -b v2 https://github.com/en-wl/wordlist.git /tmp/scowl
(cd /tmp/scowl && make)
python3 scripts/build_wordlist.py /tmp/scowl/scowl.db
```

Then run the tests and check the README examples still hold. Copy SCOWL's
`Copyright` file to `lexitron/SCOWL-Copyright.txt` if it has changed.

## Updating the pronunciations

`ry`'s pronunciations are built from the CMU Pronouncing Dictionary, for the
words in the word list, so rebuild them after updating the word list:

```sh
git clone https://github.com/cmusphinx/cmudict.git /tmp/cmudict
uv run --python 3.11 --with g2p_en --with-editable . \
    python scripts/build_pronunciations.py /tmp/cmudict
```

`g2p_en` is only needed for the build, to guess words the dictionary lacks.
Copy its `LICENSE` to `lexitron/CMUdict-License.txt` if it has changed.

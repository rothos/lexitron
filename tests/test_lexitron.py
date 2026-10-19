import sys
import pytest
from lexitron.lexitron import Lexitron, main


@pytest.fixture(scope='module')
def lx():
    return Lexitron()


@pytest.fixture
def tty(monkeypatch, capsys):
    """Make stdout look like an 80x40 terminal."""
    # pytest swaps in a fresh capture stream before the test body runs, so
    # patch the stream's class rather than the current instance.
    monkeypatch.setattr(type(sys.stdout), 'isatty', lambda self: True)
    monkeypatch.setenv('COLUMNS', '80')
    monkeypatch.setenv('LINES', '40')


def common(lx, expression, **kwargs):
    return lx.search(expression, **kwargs)['common']


# Matching

def test_matches_whole_word(lx):
    assert common(lx, 'cat') == ['cat']


def test_whole_word_applies_to_alternation(lx):
    assert common(lx, 'cat|dog') == ['cat', 'dog']


def test_explicit_anchors_still_work(lx):
    assert common(lx, '^cat$') == ['cat']


def test_substring(lx):
    words = common(lx, 'rdb', substring=True)
    assert 'birdbath' in words
    assert 'cat' not in words


def test_case_insensitive_by_default(lx):
    assert common(lx, 'DB') == ['dB', 'db']


def test_case_sensitive(lx):
    assert common(lx, 'dB', case_sensitive=True) == ['dB']
    assert common(lx, 'DB', case_sensitive=True) == []


# Wordlists

def test_proper_words_excluded_by_default(lx):
    assert lx.search('france')['proper'] == []


def test_proper_only(lx):
    matches = lx.search('france', common=False, proper=True)
    assert matches == {'common': [], 'proper': ['France']}


# Inflected forms

def test_inflected_forms_searched_by_default(lx):
    assert common(lx, 'went|geese|aardvarks') == ['aardvarks', 'geese', 'went']


def test_base_only(lx):
    assert common(lx, 'went|geese|aardvarks', base_only=True) == []
    assert common(lx, 'go|goose|aardvark', base_only=True) == ['aardvark', 'go', 'goose']


def test_variant_forms_included(lx):
    # "travelled 1", "abaci 1": variant spellings carry a level number
    assert common(lx, 'travelled|abaci') == ['abaci', 'travelled']


def test_annotated_forms_included(lx):
    # "ox N: oxen {animal}, ox 1 {animal}, oxes {oaf}"
    assert 'oxes' in common(lx, 'ox.*')


def test_questionable_forms_excluded(lx):
    # "culpabler?", "headfishes~", "abdominocentesisses<?"
    assert common(lx, 'culpabler|headfishes|abdominocentesisses') == []


def test_parse_line(lx):
    line = b'run V: ran | run | running | runs'
    assert lx.parse_line(line) == ['run', 'ran', 'run', 'running', 'runs']
    assert lx.parse_line(line, base_only=True) == ['run']


@pytest.mark.parametrize('kind', ['common', 'proper'])
def test_every_wordlist_line_parses(lx, kind):
    wordlist = getattr(lx, f'wordlist_{kind}_file')
    words = list(lx._iter_words(wordlist))
    assert len(words) > 10000
    for word in words:
        assert word
        assert not lx.QUESTIONABLE_FORM.search(word), word
        assert not set(word) & set('{}:|,'), word


# Command line output

def test_piped_output_is_one_per_line(capsys):
    main(['ca[tb]'])
    assert capsys.readouterr().out == 'cab\ncat\n'


def test_piped_no_matches_prints_nothing(capsys):
    main(['qqqq'])
    assert capsys.readouterr().out == ''


def test_piped_number(capsys):
    main(['-n', 'ca[tb]'])
    assert capsys.readouterr().out == '2\n'


def test_piped_info_goes_to_stderr(capsys):
    main(['-i', 'ca[tb]'])
    out, err = capsys.readouterr()
    assert out == 'cab\ncat\n'
    assert err == '2 matches for /ca[tb]/\n'


def test_terminal_output(capsys, tty):
    main(['-i', 'ca[tb]'])
    assert capsys.readouterr().out == '2 matches for /ca[tb]/\n\ncab\ncat\n'


def test_terminal_info_with_number_prints_header(capsys, tty):
    main(['-in', 'cat'])
    assert capsys.readouterr().out == '1 match for /cat/\n'


def test_terminal_breakdown(capsys, tty):
    main(['-inu', 'france|ship'])
    assert capsys.readouterr().out == \
        '2 matches for /france|ship/ (1 proper, 1 common)\n'


def test_invalid_regex(capsys):
    with pytest.raises(SystemExit) as exit:
        main(['('])
    assert exit.value.code == 2
    assert 'invalid regular expression' in capsys.readouterr().err


def test_uppercase_flags_are_exclusive(capsys):
    with pytest.raises(SystemExit) as exit:
        main(['-u', '-U', 'france'])
    assert exit.value.code == 2
    assert 'not allowed with' in capsys.readouterr().err

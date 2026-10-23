import sys
import pytest
from lexitron.lexitron import (load_words, letters_matcher, main,
                               parse_length, search)


@pytest.fixture
def tty(monkeypatch, capsys):
    """Make stdout look like an 80x40 terminal, without color."""
    # pytest swaps in a fresh capture stream before the test body runs, so
    # patch the stream's class rather than the current instance.
    monkeypatch.setattr(type(sys.stdout), 'isatty', lambda self: True)
    monkeypatch.setenv('COLUMNS', '80')
    monkeypatch.setenv('LINES', '40')
    monkeypatch.setenv('NO_COLOR', '1')


def common(expression='.*', **kwargs):
    return search(expression, **kwargs)['common']


# Matching

def test_matches_whole_word():
    assert common('cat') == ['cat']


def test_whole_word_applies_to_alternation():
    assert common('cat|dog') == ['cat', 'dog']


def test_explicit_anchors_still_work():
    assert common('^cat$') == ['cat']


def test_substring():
    words = common('rdb', substring=True)
    assert 'birdbath' in words
    assert 'cat' not in words


def test_case_insensitive_by_default():
    assert search('db', proper=True)['proper'] == ['dB']


def test_case_sensitive():
    assert search('dB', case_sensitive=True, proper=True)['proper'] == ['dB']
    assert search('DB', case_sensitive=True, proper=True)['proper'] == []


# Word list contents

def test_everyday_words_present():
    assert common('a|of|from|the') == ['a', 'from', 'of', 'the']


def test_all_spellings():
    assert common('colou?r') == ['color', 'colour']


def test_accents_removed():
    assert 'cafe' in common('caf.')


def test_left_out():
    # Possessives, abbreviations, letter names, contraction endings
    assert common("cat's|etc|b|q|'ll|'ve", level=95) == []


def test_fragments_left_out():
    words = search(".*", level=95, proper=True)
    for fragment in ["'n'", "o'", "h'm", "ba'", "A's", 'x']:
        assert fragment not in words['common'] + words['proper']


def test_short_words_kept():
    assert common("a|'em") == ["'em", 'a']
    assert search("i|i'm|i'd", proper=True)['proper'] == ['I', "I'd", "I'm"]


def test_contractions_kept():
    assert common("don't|'tis") == ["'tis", "don't"]


def test_proper_words_excluded_by_default():
    assert search('france')['proper'] == []


def test_proper_only():
    matches = search('france', common=False, proper=True)
    assert matches == {'common': [], 'proper': ['France']}


# Level

def test_obscure_words_need_higher_level():
    assert common('aasvogel') == []
    assert common('aasvogel', level=95) == ['aasvogel']


def test_lower_level_is_subset():
    small = set(common(level=50))
    assert small and small < set(common())


def test_word_list_is_sorted_by_size():
    sizes = [size for _, size, _, _ in load_words()]
    assert sizes == sorted(sizes)


def test_word_list_entries():
    for word, size, base_size, base_forms in load_words():
        assert word and 35 <= size <= 95
        assert base_size is None or base_size >= size
        assert base_size is not None or base_forms, word


# Phrases

def test_phrases_excluded_by_default():
    assert common('sperm whale') == []


def test_phrases():
    assert common('sperm whale', phrases=True) == ['sperm whale']
    assert 'knock-down-drag-out' in common('knock.*', phrases=True)


def test_only_phrases():
    words = common('.*cake', phrases=True, single_words=False)
    assert 'angel cake' in words
    assert 'cupcake' not in words


def test_only_phrases_flag(capsys):
    main(['-P', 'sperm wh.*'])
    assert capsys.readouterr().out == 'sperm whale\n'


def test_phrases_have_no_inflections():
    # SCOWL lists them for only a few phrases, so the word list leaves them out
    assert common('sperm banks?', phrases=True) == ['sperm bank']
    # Hyphenated words keep theirs
    assert 'x-rayed' in common('x-ray.*', phrases=True)


# Inflected forms

def test_inflected_forms_searched_by_default():
    assert common('went|geese|aardvarks') == ['aardvarks', 'geese', 'went']


def test_base_only():
    assert common('went|geese|aardvarks', base_only=True) == []
    assert common('go|goose|aardvark', base_only=True) == ['aardvark', 'go', 'goose']


# Length

@pytest.mark.parametrize('spec, expected', [
    ('5', (5, 5)), ('4-7', (4, 7)), ('5-', (5, float('inf'))), ('-7', (0, 7)),
])
def test_parse_length(spec, expected):
    assert parse_length(spec) == expected


@pytest.mark.parametrize('spec', ['', '-', 'x', '4-x', '45 7'])
def test_parse_length_invalid(spec):
    with pytest.raises(ValueError):
        parse_length(spec)


def test_length():
    words = common('ca.*', length=(3, 3))
    assert 'cat' in words
    assert all(len(word) == 3 for word in words)


def test_length_counts_letters_only():
    assert "don't" in common('don.t', length=(4, 4))


# Letters

def test_from_letters():
    assert common(letters='de') == ['de', 'ed']


def test_from_letters_counts_repeats():
    assert 'deed' not in common(letters='de')
    assert 'deed' in common(letters='deed')


def test_from_letters_with_repeat():
    words = common(letters='de', repeat=True)
    assert {'ed', 'deed', 'deeded'} <= set(words)


def test_anagram():
    assert {'stare', 'tears', 'rates'} <= set(common(letters='aerst', anagram=True))
    assert 'east' not in common(letters='aerst', anagram=True)


def test_anagram_with_repeat():
    words = common(letters='de', anagram=True, repeat=True)
    assert {'deed', 'deeded'} <= set(words)
    assert 'ed' in words


@pytest.mark.parametrize('blank', ['?', '.'])
def test_from_letters_with_blank(blank):
    words = common(letters='ct' + blank)
    assert {'cat', 'cot', 'cut', 'act', 'at', 'it'} <= set(words)
    assert 'cart' not in words
    assert 'cart' in common(letters='ct' + blank * 2)


def test_blanks_alone():
    assert common(letters='??') == common(length=(0, 2))


def test_anagram_with_blank():
    words = common(letters='ca?', anagram=True)
    assert {'cat', 'cab', 'arc', 'mac'} <= set(words)
    # The blank must be used, and so must every given letter
    assert 'ca' not in words and 'tab' not in words


def test_from_letters_with_blank_and_repeat():
    words = common(letters='de?', repeat=True)
    assert {'deeded', 'need', 'seeded'} <= set(words)
    assert 'dense' not in words  # needs two new letters


def test_letters_with_expression():
    assert common('s.*', letters='aerst', anagram=True) == ['stare']


def test_letters_matcher_ignores_case_and_punctuation():
    matches = letters_matcher('AERST')
    assert matches("ear's")
    assert not matches('eerie')


# Sorting

def test_family_sort_puts_inflections_after_base():
    words = common('r[au]n|r[au]ns|running|rang|rung|rungs|ring|rings', level=50)
    assert words == ['ring', 'rang', 'rings', 'run', 'ran', 'running', 'runs',
                     'rung', 'rungs']


def test_family_sort_leaves_lone_inflections_in_place():
    assert common('ran|rat') == ['ran', 'rat']


def test_alpha_sort():
    assert common('run|ran|runs', sort='alpha') == ['ran', 'run', 'runs']


def test_base_only_has_no_families():
    # "rung" is a base form too, so it isn't put under "ring"
    assert common('ring|rung', base_only=True) == ['ring', 'rung']


def test_sort_by_length():
    words = common('.*icide', sort='length')
    assert words[0] == 'deicide'
    assert [len(w) for w in words] == sorted(len(w) for w in words)


def test_sort_by_commonness():
    words = common('.*icide', sort='common')
    assert words.index('suicide') < words.index('aborticide')


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


def test_terminal_styles_families(capsys, tty, monkeypatch):
    monkeypatch.delenv('NO_COLOR', raising=False)
    main(['run|ran|rat|rancour'])
    common = '\033[1;38;5;34m'
    assert capsys.readouterr().out.split() == \
        [common + 'rancour\033[0m', common + 'rat\033[0m',
         common + 'run\033[0m', '\033[2mran\033[0m']


def test_terminal_colors_by_size(capsys, tty, monkeypatch):
    monkeypatch.delenv('NO_COLOR', raising=False)
    # "randy" is size 50, "ransomware" 60
    main(['-o', 'alpha', 'randy|ransomware'])
    assert capsys.readouterr().out.split() == \
        ['\033[38;5;142mrandy\033[0m', '\033[38;5;178mransomware\033[0m']


def test_no_color(capsys, tty, monkeypatch):
    monkeypatch.setenv('NO_COLOR', '1')
    main(['run|ran'])
    assert capsys.readouterr().out == 'run\nran\n'


def test_piped_output_is_not_styled(capsys):
    main(['run|ran'])
    assert capsys.readouterr().out == 'run\nran\n'


def test_terminal_info_with_number_prints_header(capsys, tty):
    main(['-in', 'cat'])
    assert capsys.readouterr().out == '1 match for /cat/\n'


def test_terminal_breakdown(capsys, tty):
    main(['-inu', 'france|ship'])
    assert capsys.readouterr().out == \
        '2 matches for /france|ship/ (1 proper, 1 common)\n'


def test_letters_header(capsys):
    main(['-i', '-a', 'aerst', 's.*'])
    assert capsys.readouterr().err == "1 match for /s.*/ anagram of 'aerst'\n"


def test_letters_without_expression(capsys):
    main(['-f', 'de'])
    assert capsys.readouterr().out == 'de\ned\n'


@pytest.mark.parametrize('argv', [
    ['-l', '4-', '-rf', 'eihnglw', '.*h.*'],
    ['-rf', 'eihnglw', '-l', '4-', '.*h.*'],
    ['-rf', 'eihnglw', '.*h.*', '-l', '4-'],
])
def test_options_anywhere(capsys, argv):
    main(argv)
    words = capsys.readouterr().out.split()
    assert 'wheeling' in words
    assert all(len(w) >= 4 and 'h' in w for w in words)


@pytest.mark.parametrize('flags', ['-rf', '-fr', '-rfx', '-frx', '-xrf'])
def test_letter_flags_bundle_in_any_order(capsys, flags):
    main([flags, 'de'])
    assert set(capsys.readouterr().out.split()) >= {'ed', 'deed', 'deeded'}


@pytest.mark.parametrize('argv, message', [
    (['('], 'invalid regular expression'),
    (['-u', '-U', 'france'], 'not allowed with'),
    (['-p', '-P', 'cake'], 'not allowed with'),
    (['-f', '-a', 'ab'], 'not allowed with'),
    ([], 'an expression is required'),
    (['cat', 'dog'], 'expected one expression'),
    (['-f'], '-f and -a take letters'),
    (['-a', 'ab', 'c', 'd'], '-f and -a take letters'),
    (['-r', 'cat'], '-r only works with -f or -a'),
    (['-l', 'x', 'cat'], 'invalid length'),
    (['-o', 'size', 'cat'], 'invalid choice'),
])
def test_usage_errors(capsys, argv, message):
    with pytest.raises(SystemExit) as exit:
        main(argv)
    assert exit.value.code == 2
    assert message in capsys.readouterr().err

import sys
import pytest
from lexitron.lexitron import search
from lexitron.rhymes import (closest, decode, derive, encode, is_arpabet,
                             load_pronunciations, long_cost, long_part, main,
                             near_cost, pronounce_query, pronunciations,
                             rhyme_key, rhyme_part, rhyme_tail, rhymes,
                             split_tail, syllables, weak_rhymes)


@pytest.fixture
def tty(monkeypatch, capsys):
    """Make stdout look like an 80x40 terminal, without color."""
    monkeypatch.setattr(type(sys.stdout), 'isatty', lambda self: True)
    monkeypatch.setenv('COLUMNS', '80')
    monkeypatch.setenv('LINES', '40')
    monkeypatch.setenv('NO_COLOR', '1')


def ry(capsys, *args):
    main(list(args))
    return capsys.readouterr().out


def words(capsys, *args):
    """ry's piped output, as a list of words."""
    return ry(capsys, *args).split()


def known(word):
    return load_pronunciations()[0].get(word)


# Pronunciations

def test_encode_round_trip():
    assert decode(encode('K AE1 T')) == 'K AE1 T'


def test_encode_rejects_unknown_phonemes():
    with pytest.raises(KeyError):
        encode('K AE T')


def test_is_arpabet():
    assert is_arpabet('K AE1 T')
    assert not is_arpabet('k ae1 t')  # lowercase is words
    assert not is_arpabet('cat')
    assert not is_arpabet('K AE0 T')  # no stressed vowel


def test_rhyme_part_from_last_stressed_vowel():
    assert decode(rhyme_part(encode('K AE1 T'))) == 'AE1 T'
    assert decode(rhyme_part(encode('D EH1 M AH0 K R AE2 T'))) == 'AE2 T'
    assert decode(rhyme_part(encode('HH AE1 P IY0'))) == 'AE1 P IY0'


def test_rhyme_part_without_stress_uses_last_vowel():
    assert decode(rhyme_part(encode('DH AH0'))) == 'AH0'


def test_rhyme_part_skips_unstressed_uh_marked_secondary():
    # CMUdict: "additionally" AH0 D IH1 SH AH0 N AH2 L IY0
    assert decode(rhyme_part(encode('AH0 D IH1 SH AH0 N AH2 L IY0'))) \
        == 'IH1 SH AH0 N AH2 L IY0'
    assert decode(rhyme_part(encode('G AA1 G AH2'))) == 'AA1 G AH2'
    # but "backup" rhymes with "cup"
    assert decode(rhyme_part(encode('B AE1 K AH2 P'))) == 'AH2 P'


def test_rhyme_key_ignores_stress_and_reduced_vowels():
    assert rhyme_key(encode('K AE1 T')) == rhyme_key(encode('B AE2 T'))
    assert rhyme_key(encode('AO1 R AH0 N JH')) == rhyme_key(encode('AO1 R IH0 N JH'))


def test_syllables():
    assert syllables(encode('AE1 K R AH0 B AE2 T')) == 3


def test_bundled_pronunciations():
    assert decode(known('cat')[0]) == 'K AE1 T'
    assert {decode(p) for p in known('read')} == {'R IY1 D', 'R EH1 D'}


def test_every_word_has_a_pronunciation():
    missing = [w for w in search('.*', level=60, sort='alpha')['common']
               if not pronunciations(w)]
    assert missing == []


def test_phrase_pronunciation():
    assert decode(pronunciations('sperm whale')[0]).startswith('S P ER1 M')


# Deriving pronunciations

def lookup(table):
    table = {w: (encode(p),) for w, p in table.items()}
    return table.get


def is_any_word(word):
    return True


@pytest.mark.parametrize('word, base, arpabet, expected', [
    ('chasms', 'chasm', 'K AE1 Z AH0 M', 'K AE1 Z AH0 M Z'),
    ('cats', 'cat', 'K AE1 T', 'K AE1 T S'),
    ('horses', 'horse', 'HH AO1 R S', 'HH AO1 R S IH0 Z'),
    ('loafed', 'loaf', 'L OW1 F', 'L OW1 F T'),
    ('rained', 'rain', 'R EY1 N', 'R EY1 N D'),
    ('wanted', 'want', 'W AA1 N T', 'W AA1 N T IH0 D'),
    ('hoping', 'hope', 'HH OW1 P', 'HH OW1 P IH0 NG'),
    ('hopped', 'hop', 'HH AA1 P', 'HH AA1 P T'),
    ('happily', 'happy', 'HH AE1 P IY0', 'HH AE1 P AH0 L IY0'),
    ('belfries', 'belfry', 'B EH1 L F R IY0', 'B EH1 L F R IY0 Z'),
    ('humanise', 'humanize', 'HH Y UW1 M AH0 N AY2 Z', 'HH Y UW1 M AH0 N AY2 Z'),
    ('colours', 'color', 'K AH1 L ER0', 'K AH1 L ER0 Z'),
])
def test_derive(word, base, arpabet, expected):
    found = derive(word, lookup({base: arpabet}), is_any_word)
    assert decode(found[0]) == expected


def test_derive_prefers_the_e_word():
    # "hoped" is from "hope", not "hop"
    found = derive('hoped', lookup({'hop': 'HH AA1 P', 'hope': 'HH OW1 P'}),
                   is_any_word)
    assert decode(found[0]) == 'HH OW1 P T'


def test_derive_compound_stresses_the_first_word():
    found = derive('sheepherder', lookup({'sheep': 'SH IY1 P',
                                          'herder': 'HH ER1 D ER0'}),
                   is_any_word)
    assert decode(found[0]) == 'SH IY1 P HH ER2 D ER0'


def test_derive_compound_with_particle():
    found = derive('mashup', lookup({'mash': 'M AE1 SH', 'up': 'AH1 P'}),
                   is_any_word)
    assert decode(found[0]) == 'M AE1 SH AH2 P'


def test_derive_short_compound_parts_must_be_common():
    table = lookup({'sec': 'S EH1 K', 'ant': 'AE1 N T'})
    assert derive('secant', table, is_any_word, lambda w: False) == ()


def test_derive_needs_real_words():
    assert derive('hoped', lookup({'hop': 'HH AA1 P'}),
                  lambda w: w != 'hop') == ()


def test_derive_gives_up():
    assert derive('zzzxq', lookup({}), is_any_word) == ()


# Near rhymes

def cost(a, b, **kwargs):
    return near_cost(rhyme_part(encode(a)), rhyme_part(encode(b)), **kwargs)


def test_perfect_rhyme_costs_nothing():
    assert cost('K AE1 T', 'B AE1 T') == 0


def test_voicing_is_close():
    assert cost('L AH1 V', 'R AH1 F') == pytest.approx(0.25)


def test_added_ending_is_close():
    assert cost('K AE1 T', 'K AE1 S T') == pytest.approx(0.35)


def test_ending_on_a_vowel_is_further():
    assert cost('L AH1 V', 'D AH1') > cost('L AH1 V', 'R AH1 F')


def test_different_stressed_vowel_isnt_near():
    assert cost('K AE1 T', 'K IY1 T') is None


def test_syllables_must_match():
    assert cost('K AE1 T', 'K AE1 T AH0 L') is None


def test_assonance_needs_the_same_vowels():
    assert cost('T AY1 M', 'L AY1 T', assonance=True) is not None
    assert cost('T AY1 M', 'L OW1 T', assonance=True) is None


def test_closest_keeps_close_ones():
    found = [(f'w{i}', 1, 0.5) for i in range(40)] + [('far', 1, 0.9)]
    assert ('far', 1, 0.9) not in closest(found)


def test_closest_reaches_further_when_there_are_few():
    found = [('near', 1, 0.5), ('far', 1, 0.9)]
    assert closest(found) == found


# Long rhymes, tails and phrases

def test_rhyme_tail_can_be_longer_than_rhyme_part():
    assert rhyme_tail(encode('K ER1 F Y UW2'), 2) == encode('ER1 F Y UW2')
    assert rhyme_tail(encode('K ER1 F Y UW2'), 3) is None


def test_rhyme_tail_needs_a_stressed_start():
    assert rhyme_tail(encode('T AE0 T UW1'), 2) is None


def test_rhyme_tail_rejects_a_stronger_stress_later():
    assert rhyme_tail(encode('HH IH1 DH ER2 T UW1'), 2) is None


def test_long_part():
    assert long_part(known('education')[0]) == encode('EH2 JH AH0 K EY1 SH AH0 N')
    assert long_part(known('cat')[0]) is None


def test_long_part_counts_secondary_uh():
    assert decode(long_part(known('understand')[0])).startswith('AH2')


def test_long_cost():
    education = known('education')[0]
    assert long_cost(education, known('dedication')[0]) < long_cost(
        education, known('celebration')[0])
    assert long_cost(education, known('nation')[0]) is None
    assert long_cost(education, known('vacation')[0]) is None


def test_phrases_leave_little_words_unstressed():
    assert pronunciations('hurt you') == (encode('HH ER1 T Y UW0'),)


def test_phrases_of_only_little_words_keep_the_last_stressed():
    assert decode(pronunciations('of you')[0]).endswith('UW1')


def test_t_and_you_run_together():
    assert rhyme_key(pronunciations('hurt you')[0]) == rhyme_key(known('virtue')[0])
    assert rhyme_key(pronunciations('miss you')[0]) == rhyme_key(known('tissue')[1])


def test_near_cost_without_running_together():
    hurt_you = rhyme_part(pronunciations('hurt you')[0])
    assert near_cost(hurt_you, encode('ER1 F Y UW0')) is not None


def test_split_tail():
    assert split_tail('hurt you') == ('hurt', 'you')
    assert split_tail('give it to me') == ('give', 'it to me')
    assert split_tail('make it rain') is None
    assert split_tail('of you') is None


# Finding rhymes

def test_rhymes():
    found = {w for w, _, _ in rhymes(known('cat'), ['bat', 'acrobat', 'dog', 'cat'],
                                     exclude=['cat'])}
    assert found == {'bat', 'acrobat'}


def test_rhymes_leave_out_homophones():
    found = {w for w, _, _ in rhymes(known('write'), ['right', 'rite', 'bite'])}
    assert found == {'bite'}


def test_near_rhymes_leave_out_perfect_ones():
    found = {w for w, _, _ in rhymes(known('love'), ['glove', 'rough'], 'near')}
    assert found == {'rough'}


def test_wrenched_rhymes():
    candidates = ['philosophy', 'agree', 'democracy', 'fluffy', 'happy']
    assert {w for w, _, _ in rhymes(known('be'), candidates,
                                    wrenched=True)} == {
        'philosophy', 'democracy', 'fluffy', 'happy'}
    # Unstressed on both sides doesn't count; "fluffy" is stressed where
    # "philosophy" isn't
    assert {w for w, _, _ in rhymes(known('philosophy'), candidates,
                                    wrenched=True)} == {'agree', 'fluffy'}


def test_wrenched_assonance():
    candidates = ['carried', 'always', 'philosophy', 'beat', 'agree']
    # Not "philosophy", a perfect wrenched rhyme, or "beat", stressed like
    # "be" (B IY1, and B IY0 is just "be" said quickly)
    assert {w for w, _, _ in rhymes(known('be'), candidates, 'assonance',
                                    wrenched=True)} == {'carried', 'always'}


def test_unstressed_words_dont_rhyme():
    found = {w for w, _, _ in rhymes(known('ago'), ['a', 'go'])}
    assert 'a' not in found


def test_weak_rhymes():
    weak = weak_rhymes(['bobcat', 'bat', 'cats', 'bats'], known('cat'), 'cat',
                       inflections=True)
    assert weak == {'bobcat', 'cats', 'bats'}


def test_weak_rhymes_without_inflections():
    assert weak_rhymes(['bats'], known('cat'), 'cat') == set()


def test_pronounce_query_unknown_word_sounds_like_known_one():
    prons, notes = pronounce_query('blorange')
    assert prons == known('orange')
    assert notes == ["guessing 'blorange' sounds like 'orange'"]


def test_pronounce_query_arpabet():
    assert pronounce_query('K AE1 T') == ((encode('K AE1 T'),), [])


# The command line

def test_cli_piped(capsys):
    found = words(capsys, 'cat')
    assert 'hat' in found and 'acrobat' in found and 'cat' not in found
    assert found.index('hat') < found.index('acrobat')


def test_cli_weak_rhymes_last(capsys):
    found = words(capsys, '-y', '2', 'cat')
    assert found.index('format') < found.index('bobcat')


def test_cli_syllables(capsys):
    assert set(words(capsys, '-y', '3', 'cat')) >= {'acrobat', 'democrat'}
    assert 'hat' not in words(capsys, '-y', '2-', 'cat')


def test_cli_expression(capsys):
    assert words(capsys, 'cat', 'b.*') == ['bat', 'brat', 'brickbat',
                                          'backchat', 'bathmat', 'begat',
                                          'bobcat', 'bureaucrat', 'babysat',
                                          'butterfat']


def test_cli_count(capsys):
    assert int(ry(capsys, '-n', 'cat')) > 50


def test_cli_near(capsys):
    found = words(capsys, '-N', 'love')
    assert {'rough', 'stuff', 'enough'} <= set(found)
    assert 'glove' not in found


def test_cli_wrenched(capsys):
    found = words(capsys, '-w', '-y', '4', 'be')
    assert {'philosophy', 'democracy', 'biology'} <= set(found)
    assert 'interviewee' not in found


def test_cli_wrenched_with_near_and_assonance(capsys):
    found = words(capsys, '-w', '-A', '-y', '2', 'be')
    assert {'always', 'carried'} <= set(found)
    assert 'happy' not in found and 'beat' not in found
    assert 'shows' in words(capsys, '-w', '-N', 'window')


def test_cli_wrenched_header(tty, capsys):
    out = ry(capsys, '-I', '-n', '-w', '-A', 'be')
    assert " wrenched assonant words for 'be' " in out


def test_cli_wrenched_phrase_ending_in_little_words(capsys):
    assert 'comfort you' in ry(capsys, '-w', '-L', '50', 'hurt you').splitlines()


def test_cli_final_y_is_unstressed(capsys):
    # The CMU Pronouncing Dictionary stresses a few, for no reason
    found = words(capsys, '-L', '95', 'be')
    assert 'ability' not in found and 'gutsy' not in found
    assert 'interviewee' in found


def test_cli_falls_back_to_near_rhymes(capsys):
    main(['orange'])
    captured = capsys.readouterr()
    assert {'porridge', 'storage', 'foreign'} <= set(captured.out.split())
    assert "no perfect rhymes for 'orange'; showing near rhymes" in captured.err


def test_cli_fallback_note(capsys):
    main(['month'])
    captured = capsys.readouterr()
    assert "no perfect rhymes for 'month' but twelvemonth" in captured.err
    assert 'done' in captured.out.split()


def test_cli_phrase(capsys):
    assert 'brain' in words(capsys, 'make it rain')


def test_cli_phrase_ending_in_little_words(capsys):
    found = ry(capsys, 'hurt you').split('\n')
    assert 'virtue' in found
    assert {'desert you', 'alert you'} <= set(found)
    assert 'dirt you' not in found


def test_cli_phrase_ending_in_little_words_near(capsys):
    found = ry(capsys, '-N', 'hurt you').split('\n')
    assert {'curfew', 'curse you', 'nurse you'} <= set(found)
    assert 'desert you' not in found


def test_cli_rhymes_with_later_secondary_stress(capsys):
    # P ER1 V Y UW2, though its rhyme part is UW2
    assert 'purview' in words(capsys, '-N', 'hurt you')


def test_cli_proper(capsys):
    assert 'Ferris' not in words(capsys, 'Paris')
    assert 'Ferris' in words(capsys, '-u', 'Paris')


def test_cli_phrases(capsys):
    assert 'fat cat' in ry(capsys, '-P', 'cat').split('\n')


def test_terminal_groups_by_syllables(tty, capsys):
    out = ry(capsys, '-L', '40', 'cat')
    assert out.startswith('1 syllable\n')
    assert '\n2 syllables\n' in out
    assert '\n4 syllables\naristocrat\n' in out


def test_terminal_sections_for_each_pronunciation(tty, capsys):
    out = ry(capsys, '-y', '1', '-L', '35', 'read')
    assert 'read (R IY1 D)' in out and 'read (R EH1 D)' in out


def test_terminal_info(tty, capsys):
    out = ry(capsys, '-I', '-n', 'cat')
    assert out.endswith(" rhymes for 'cat' (K AE1 T)\n")
    assert int(out.split()[0]) > 50


def test_terminal_notes(tty, capsys):
    assert ry(capsys, 'blorange').startswith(
        "(guessing 'blorange' sounds like 'orange')")


def test_terminal_long_rhymes_first(tty, capsys):
    out = ry(capsys, '-L', '50', 'understand')
    assert out.startswith('long rhymes\n')
    first = out.split('\n\n')[0]
    assert 'wonderland' in first and 'grand' not in first


def test_terminal_few_perfect_rhymes_add_near_ones(tty, capsys):
    out = ry(capsys, '-L', '40', 'hurt you')
    assert '\nnear rhymes\n' in out and 'curfew' in out
    assert '\n… you\n' in out


def test_near_rhymes_not_added_when_narrowed(tty, capsys):
    assert 'near rhymes' not in ry(capsys, '-y', '2', 'hurt you')


def test_near_rhymes_not_added_when_piped(capsys):
    assert 'curfew' not in words(capsys, 'hurt you')


def test_terminal_common_order_is_flat(tty, capsys):
    assert 'syllable' not in ry(capsys, '-o', 'common', 'cat')


@pytest.mark.parametrize('args, message', [
    ([], 'give a word'),
    (['cat', 'b.*', 'more'], 'give a word'),
    (['-y', 'x', 'cat'], "invalid syllables: 'x'"),
    (['-N', '-A', 'cat'], 'not allowed with'),
    (['zzzxq'], "can't tell how to pronounce"),
    (['cat', '('], 'invalid regular expression'),
    (['-t', 'a*', 'cat'], 'invalid pattern'),
])
def test_usage_errors(capsys, args, message):
    with pytest.raises(SystemExit):
        main(args)
    assert message in capsys.readouterr().err

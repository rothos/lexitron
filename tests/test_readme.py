"""Check that every `$ lx ...` example in the README gives the output shown."""

import re
import shlex
import sys
from pathlib import Path

import pytest
from lexitron.lexitron import main

README = Path(__file__).resolve().parent.parent / 'README.md'


def examples():
    for block in re.findall(r'^```\n(.*?)^```', README.read_text(), re.M | re.S):
        command, _, expected = block.partition('\n')
        # Skip the usage synopsis, e.g. "$ lx [options] expression"
        if command.startswith('$ lx ') and '[options]' not in command:
            yield pytest.param(command[2:], expected, id=command[2:])


@pytest.mark.parametrize('command, expected', list(examples()))
def test_readme_example(command, expected, capsys, monkeypatch):
    command, *pipe = command.split(' | ')
    argv = shlex.split(command)[1:]

    # Examples without a pipe show what you'd see in an 80x30 terminal
    if not pipe:
        monkeypatch.setattr(type(sys.stdout), 'isatty', lambda self: True)
        monkeypatch.setenv('COLUMNS', '80')
        monkeypatch.setenv('LINES', '30')
        monkeypatch.setenv('NO_COLOR', '1')

    main(argv)
    out, err = capsys.readouterr()
    lines = (err + out).splitlines()

    for step in pipe:
        tool, *count = shlex.split(step)
        n = int(count[0].lstrip('-')) if count else 10
        lines = lines[:n] if tool == 'head' else lines[-n:]

    assert lines == expected.splitlines()

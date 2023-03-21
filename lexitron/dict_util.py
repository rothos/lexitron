# This python script is a utility to separate large dictionary files
# into lowercase and uppercase (common and proper) parts.
# These parts are written to two new files.

import sys
from importlib import resources

dictfile = 'words.txt'
with open(dictfile, 'rb') as f:
    words = f.read()
f.close()

words = words.splitlines()
words = [word.decode('utf-8') for word in words]

lowercase = []
uppercase = []

for word in words:
    word = word.strip()

    # If there is any punctuation in the word, skip it
    if not word.isalpha():
        continue

    if word[0].islower():
        lowercase.append(word)

    elif word[0].isupper():
        uppercase.append(word)

    else:
        print("Error: {} is neither lowercase nor uppercase".format(word))

lowercase = [word for word in lowercase]
uppercase = [word for word in uppercase]

lowercase_file = 'words-lower.txt'
uppercase_file = 'words-upper.txt'

with open(lowercase_file, 'w') as f:
    f.write("\n".join(lowercase))
f.close()

with open(uppercase_file, 'w') as f:
    f.write("\n".join(uppercase))
f.close()

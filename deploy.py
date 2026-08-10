import argparse
import base64
import hashlib
from dataclasses import dataclass, field

import opencc
from Crypto.Cipher import AES


PRIVATE_WORDS_HEAD = """
---
name: private.words
version: "2025.06.01"
sort: by_weight
...

"""

CHONGKIT_HEAD = """
---
name: chongkit.words
version: "2025.06.01"
sort: by_weight
...

"""

KEYBOARD = "日月金木水火土竹戈十大中一弓人心手口尸廿山女田的卜我"


@dataclass
class Context:
    converter: opencc.OpenCC
    debug: bool = False
    whitelist: set = field(default_factory=set)
    blacklist: set = field(default_factory=set)
    char_lookup: dict = field(default_factory=dict)
    code_lookup: dict = field(default_factory=dict)


def decrypt_string(key_string, encoded_data):
    key = hashlib.sha256(key_string.encode()).digest()
    decoded_data = base64.b64decode(encoded_data)
    nonce_len = 16
    tag_len = 16
    nonce = decoded_data[:nonce_len]
    tag = decoded_data[nonce_len:nonce_len + tag_len]
    ciphertext = decoded_data[nonce_len + tag_len:]
    cipher = AES.new(key, AES.MODE_GCM, nonce=nonce)
    plaintext_bytes = cipher.decrypt_and_verify(ciphertext, tag)
    return plaintext_bytes.decode('utf-8')


def decrypt_file(secret, src, dst, header=None):
    with open(dst, mode="w") as out:
        if header:
            out.write(header)
        with open(src, mode="r") as encrypted:
            for line in encrypted:
                if len(line) > 1:
                    out.write(decrypt_string(secret, line) + "\n")


def dict_section(path):
    """Yield stripped, non-empty lines that follow the `...` marker."""
    with open(path, mode="r") as lines:
        started = False
        for line in lines:
            line = line[:-1]
            if line == "":
                continue
            if line == "...":
                started = True
                continue
            if started:
                yield line


def parse_code(parts):
    """Return (full, abbr) from a dict row, honoring an optional column 3."""
    full = parts[1]
    abbr = full
    if len(parts) > 2:
        full = parts[2].replace("'", "")
        abbr = parts[2].split("'")[0]
    return full, abbr


def single_key(code):
    i = ord(code) - 97
    return KEYBOARD[i]


def should_exclude(combined_code, word, simplified, ctx):
    char_lookup = ctx.char_lookup
    if (len(combined_code) == 5
        and combined_code[:3] in char_lookup
        and (combined_code[:1] + combined_code[2:3]
             not in char_lookup or
             char_lookup[combined_code[:1] + combined_code[2:3]]
             != char_lookup[combined_code[:3]])
            # 緊接 「着」「的」等高頻後置字
            and combined_code[3:] in ["tu", "ha"]):
        if simplified in ctx.whitelist and ctx.debug:
            print(char_lookup[combined_code[:3]] + "\t" + word)
    return (len(combined_code) >= 5
            and combined_code[:3] in char_lookup
            and (combined_code[:1] + combined_code[2:3]
                 not in char_lookup or
                 char_lookup[combined_code[:1] + combined_code[2:3]]
                 != char_lookup[combined_code[:3]])
            and simplified not in ctx.whitelist)


def append_dictionary_entry(dictionary, word, combined_code, ctx):
    char_lookup = ctx.char_lookup
    suffix_x = ""
    suffix = ""
    if len(combined_code) <= 4:
        suffix_x = "x"
    if len(combined_code) > 3 and combined_code[:4] in char_lookup:
        if not suffix_x:
            suffix = "'"
        if len(combined_code) == 5:
            dictionary.append(char_lookup[combined_code[:4]]
                              + single_key(combined_code[4:5]) + "\t"
                              + combined_code[:5] + "'")
    elif combined_code[:3] in char_lookup:
        if len(combined_code) == 4:
            if not suffix_x:
                suffix = "'"
            dictionary.append(char_lookup[combined_code[:3]]
                              + single_key(combined_code[3:4]) + "\t"
                              + combined_code[:4] + "'")
        elif len(combined_code) == 5:
            dictionary.append(char_lookup[combined_code[:3]]
                              + single_key(combined_code[3:4]) + "\t"
                              + combined_code[:4] + "'")
    dictionary.append(word + "\t" + combined_code + suffix_x + suffix)
    if suffix_x:
        dictionary.append(word + "\t" + combined_code + "'")


def n_char_word(word, simplified, ctx):
    code_lookup = ctx.code_lookup
    dictionary = []
    for code1 in code_lookup[word[0]]:
        for code2 in code_lookup[word[1]]:
            for code3 in code_lookup[word[2]]:
                for code4 in code_lookup[word[-2]]:
                    for code_n in code_lookup[word[-1]]:
                        full1, abbr1 = code1
                        full2, abbr2 = code2
                        full3, abbr3 = code3
                        full4, abbr4 = code4
                        full_n, abbr_n = code_n
                        combined_code = full1[0] + abbr2[-1] + abbr3[0]
                        combined_code += abbr4[-1] + abbr_n[-1]
                        if should_exclude(combined_code, word, simplified,
                                          ctx):
                            continue
                        append_dictionary_entry(dictionary, word,
                                                combined_code, ctx)
    return dictionary


def _4_char_word(word, simplified, ctx):
    code_lookup = ctx.code_lookup
    dictionary = []
    for code1 in code_lookup[word[0]]:
        for code2 in code_lookup[word[1]]:
            for code3 in code_lookup[word[2]]:
                for code4 in code_lookup[word[3]]:
                    full1, abbr1 = code1
                    full2, abbr2 = code2
                    full3, abbr3 = code3
                    full4, abbr4 = code4
                    combined_code = full1[0] + abbr2[-1] + abbr3[0]
                    if len(abbr3) == 1 and len(full3) > 1:
                        combined_code += full3[-1] + abbr4[-1]
                    elif len(abbr3) > 1:
                        combined_code += abbr3[-1] + abbr4[-1]
                    elif len(abbr4) > 1:
                        combined_code += abbr4[0] + abbr4[-1]
                    elif len(full4) > 1:
                        combined_code += full4[0] + full4[-1]
                    else:
                        combined_code += abbr4[-1]
                    if should_exclude(combined_code, word, simplified, ctx):
                        continue
                    append_dictionary_entry(dictionary, word, combined_code,
                                            ctx)
    return dictionary


def _2_char_word(word, simplified, ctx):
    code_lookup = ctx.code_lookup
    dictionary = []
    for code1 in code_lookup[word[0]]:
        for code2 in code_lookup[word[1]]:
            full1, abbr1 = code1
            full2, abbr2 = code2
            if len(abbr1) == 1 and len(full1) != 1:
                combined_code = full1[0] + full1[-1]
            elif len(full1) == 1:
                combined_code = full1
            else:
                combined_code = abbr1[0] + abbr1[-1]

            if len(abbr2) <= 2 and len(full2) > 2:
                combined_code += full2[0] + full2[1] + full2[-1]
            elif len(abbr2) == 2:
                combined_code += abbr2[0] + abbr2[1]
            elif len(abbr2) == 1 and len(full2) == 2:
                combined_code += full2[0] + full2[1]
            elif len(abbr2) == 1 and len(full2) > 2:
                combined_code += full2[0] + full2[1] + full2[-1]
            elif len(abbr2) == 1:
                combined_code += abbr2[0]
            else:
                combined_code += abbr2[0] + abbr2[1] + abbr2[-1]
            if should_exclude(combined_code, word, simplified, ctx):
                continue
            append_dictionary_entry(dictionary, word, combined_code, ctx)
    return dictionary


def _3_char_word(word, simplified, ctx):
    code_lookup = ctx.code_lookup
    dictionary = []
    for code1 in code_lookup[word[0]]:
        for code2 in code_lookup[word[1]]:
            for code3 in code_lookup[word[2]]:
                full1, abbr1 = code1
                full2, abbr2 = code2
                full3, abbr3 = code3
                if len(abbr1) == 1 and len(full1) != 1:
                    combined_code = full1[0] + full1[-1]
                elif len(full1) == 1:
                    combined_code = full1
                else:
                    combined_code = abbr1[0] + abbr1[-1]

                occupied_by_mid = 0
                if len(abbr2) == 1 and len(full2) != 1:
                    combined_code += full2[0] + full2[-1]
                    occupied_by_mid = 2
                elif len(full2) == 1:
                    combined_code += full2
                    occupied_by_mid = 1
                else:
                    combined_code += abbr2[0] + abbr2[-1]
                    occupied_by_mid = 2

                if occupied_by_mid == 2 or len(full3) == 1:
                    combined_code += abbr3[-1]
                else:
                    if len(full3) > 1 and len(abbr3) == 1:
                        combined_code += full3[0] + full3[-1]
                    elif len(abbr3) == 1:
                        combined_code += abbr3[-1]
                    else:
                        combined_code += abbr3[0] + abbr3[-1]
                if should_exclude(combined_code, word, simplified, ctx):
                    continue
                append_dictionary_entry(dictionary, word, combined_code, ctx)
    return dictionary


def generate_dictionary_entries(word, ctx):
    if any(c not in ctx.code_lookup for c in word):
        return []
    if word in ctx.blacklist:
        return []
    simplified = ctx.converter.convert(word)
    n = len(word)
    if n == 2:
        return _2_char_word(word, simplified, ctx)
    if n == 3:
        return _3_char_word(word, simplified, ctx)
    if n == 4:
        return _4_char_word(word, simplified, ctx)
    if n > 4:
        return n_char_word(word, simplified, ctx)
    return []


def read_words(path, target, must_include, ctx):
    with open(path, mode="r") as f:
        for line in f:
            line = line[:-1].split("\t")
            word = line[0]
            if len(word) <= 1:
                continue
            weight = int(line[1])
            target.append([word, weight])
            if must_include:
                ctx.whitelist.add(ctx.converter.convert(word))


def output_dictionary(path, mode, items, ctx, header=None):
    with open(path, mode=mode) as out:
        if header:
            out.write(header)
        for word, _ in items:
            for entry in generate_dictionary_entries(word, ctx):
                out.write(entry + "\n")


def load_whitelist(ctx, path):
    for line in dict_section(path):
        parts = line.split("\t")
        if len(parts[0]) > 1:
            ctx.whitelist.add(parts[0])


def load_blacklist(ctx, path):
    with open(path, mode="r") as f:
        for line in f:
            ctx.blacklist.add(line[:-1])


def load_char_lookup(ctx, path):
    for line in dict_section(path):
        parts = line.split("\t")
        char = parts[0]
        if len(char) > 1:
            continue
        full = parts[1]
        if full.startswith("x"):
            break
        if full.endswith("'"):
            continue
        ctx.char_lookup[full] = char


def load_code_lookup(ctx, cangjie_path, fix_path):
    for line in dict_section(cangjie_path):
        parts = line.split("\t")
        char = parts[0]
        if parts[1].startswith("x"):
            break
        full, abbr = parse_code(parts)
        ctx.code_lookup.setdefault(char, []).append([full, abbr])
    with open(fix_path, mode="r") as f:
        for line in f:
            parts = line[:-1].split("\t")
            char = parts[0]
            full, abbr = parse_code(parts)
            ctx.code_lookup[char] = [[full, abbr]]


def main():
    parser = argparse.ArgumentParser(description="Build Chongkit dictionaries")
    parser.add_argument("--debug", action="store_true",
                        help="print whitelist-maintenance diagnostics")
    args = parser.parse_args()

    ctx = Context(converter=opencc.OpenCC('t2s.json'), debug=args.debug)

    secret = open("private.words.secret", mode="r").read()
    decrypt_file(secret, "private.words.dict.encrypted",
                 "private.words.dict.yaml", PRIVATE_WORDS_HEAD)
    decrypt_file(secret, "private.essay.encrypted", "private.essay.txt")

    load_whitelist(ctx, "tigress_ci.dict.yaml")
    load_blacklist(ctx, "blacklist.txt")
    load_char_lookup(ctx, "tingkung.dict.yaml")
    load_code_lookup(ctx, "cangjie5.dict.yaml", "fix.txt")

    words = []
    private_words = []
    read_words("essay.txt", words, False, ctx)
    read_words("essay-cantonese.txt", words, False, ctx)
    read_words("custom-essay.txt", words, True, ctx)
    read_words("private.essay.txt", private_words, True, ctx)
    words.sort(key=lambda x: -x[1])
    private_words.sort(key=lambda x: -x[1])

    output_dictionary("chongkit.words.dict.yaml", "w", words, ctx,
                      CHONGKIT_HEAD)
    output_dictionary("private.words.dict.yaml", "a", private_words, ctx)


if __name__ == "__main__":
    main()

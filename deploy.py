import opencc
converter = opencc.OpenCC('t2s.json')

head = """
---
name: chongkit.words
version: "2025.06.01"
sort: by_weight
...

"""


def single_key(code):
    keyboard = "日月金木水火土竹戈十大中一弓人心手口尸廿山女田的卜我"
    i = ord(code) - 97
    return keyboard[i]


candidates = open("tigress_ci.dict.yaml", mode="r")

candidates_set = set()

start = False
for line in candidates:
    line = line[:-1]
    if line == "":
        continue
    if line == "...":
        start = True
        continue
    if not start:
        continue
    line = line.split("\t")
    if len(line[0]) > 1:
        candidates_set.add(line[0])

blacklist = open("blacklist.txt", mode="r")

blacklist_set = set()

for line in blacklist:
    line = line[:-1]
    blacklist_set.add(line)


def append_res(res, combined_code):
    suffix_x = ""
    suffix = ""
    if len(combined_code) <= 4:
        suffix_x = "x"
    if len(combined_code) > 3 and combined_code[:4] in tingkung_code2char:
        if not suffix_x:
            suffix = "'"
        if len(combined_code) == 5:
            res.append(tingkung_code2char[combined_code[:4]]
                       + single_key(combined_code[4:5]) + "\t"
                       + combined_code[:5] + "'")
    elif combined_code[:3] in tingkung_code2char:
        if len(combined_code) == 4:
            if not suffix_x:
                suffix = "'"
            res.append(tingkung_code2char[combined_code[:3]]
                       + single_key(combined_code[3:4]) + "\t"
                       + combined_code[:4] + "'")
        elif len(combined_code) == 5:
            res.append(tingkung_code2char[combined_code[:3]]
                       + single_key(combined_code[3:4]) + "\t"
                       + combined_code[:4] + "'")
    res.append(word + "\t" + combined_code + suffix_x + suffix)
    if suffix_x:
        res.append(word + "\t" + combined_code + "'")


def n_chars_word(word, map, tingkung_code2char):
    if len(word) <= 4:
        return None
    for c in word:
        if c not in map:
            return None
    if word in blacklist_set:
        return None
    res = []
    for code1 in map[word[0]]:
        for code2 in map[word[1]]:
            for code3 in map[word[2]]:
                for code4 in map[word[-2]]:
                    for code_n in map[word[-1]]:
                        full1, abbr1 = code1
                        full2, abbr2 = code2
                        full3, abbr3 = code3
                        full4, abbr4 = code4
                        full_n, abbr_n = code_n
                        combined_code = full1[0] + abbr2[-1] + abbr3[0]
                        combined_code += abbr4[-1] + abbr_n[-1]
                        if do_filter(combined_code):
                            continue
                        append_res(res, combined_code)
    return res


def _4_chars_word(word, map, tingkung_code2char):
    if len(word) != 4:
        return None
    for c in word:
        if c not in map:
            return None
    if word in blacklist_set:
        return None
    res = []
    for code1 in map[word[0]]:
        for code2 in map[word[1]]:
            for code3 in map[word[2]]:
                for code4 in map[word[3]]:
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
                    else:
                        combined_code += abbr4[-1]
                    if do_filter(combined_code):
                        continue
                    append_res(res, combined_code)
    return res


def _2_chars_word(word, map, tingkung_code2char):
    if len(word) != 2:
        return None
    if word[0] not in map or word[1] not in map:
        return None
    if word in blacklist_set:
        return None
    res = []
    for code1 in map[word[0]]:
        for code2 in map[word[1]]:
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
            if do_filter(combined_code):
                continue
            append_res(res, combined_code)
    return res


def _3_chars_word(word, map, tingkung_code2char):
    if len(word) != 3:
        return None
    if word[0] not in map or word[1] not in map or word[2] not in map:
        return None
    if word in blacklist_set:
        return None
    res = []
    for code1 in map[word[0]]:
        for code2 in map[word[1]]:
            for code3 in map[word[2]]:
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
                if do_filter(combined_code):
                    continue
                append_res(res, combined_code)
    return res


essay = open("essay.txt", mode="r")
cangjie = open("cangjie5.dict.yaml", mode="r")
tingkung = open("tingkung.dict.yaml", mode="r")

tingkung_code2char = {}
tingkung_char2code = {}

start = False
for line in tingkung:
    line = line[:-1]
    if line == "":
        continue
    if line == "...":
        start = True
        continue
    if start:
        line = line.split("\t")
        char = line[0]
        if len(char) > 1:
            continue
        full = line[1]
        if full.startswith("x"):
            start = False
            continue
        if full.endswith("'"):
            continue
    if not start:
        continue
    if char in tingkung_char2code:
        tingkung_char2code[char].append(full)
    else:
        tingkung_char2code[char] = []
        tingkung_char2code[char].append(full)
    tingkung_code2char[full] = char


arr = []
map = {}

start = False
for line in cangjie:
    line = line[:-1]
    if line == "":
        continue
    if line == "...":
        start = True
        continue
    if start:
        line = line.split("\t")
        char = line[0]
        full = line[1]
        abbr = full
        if full.startswith("x"):
            start = False
            continue
        if len(line) > 2:
            full = line[2].replace("'", "")
            abbr = line[2].split("'")[0]
    if not start:
        continue
    if char in map:
        map[char].append([full, abbr])
    else:
        map[char] = []
        map[char].append([full, abbr])

fix = open("fix.txt", mode="r")
for line in fix:
    line = line[:-1]
    line = line.split("\t")
    char = line[0]
    full = line[1]
    abbr = full
    if len(line) > 2:
        full = line[2].replace("'", "")
        abbr = line[2].split("'")[0]
    map[char] = []
    map[char].append([full, abbr])

for line in essay:
    line = line[:-1]
    line = line.split("\t")
    word = line[0]
    if len(word) <= 1:
        continue
    weight = int(line[1])
    arr.append([word, weight])
arr.sort(key=lambda x: -x[1])

with open("chongkit.words.dict.yaml", mode="w") as words:
    words.writelines(head)
    for item in arr:
        word = item[0]
        weight = item[1]
        lines = _2_chars_word(word, map, tingkung_code2char)
        if lines:
            for line in lines:
                words.write(line + "\n")
        lines = _3_chars_word(word, map, tingkung_code2char)
        if lines:
            for line in lines:
                words.write(line + "\n")
        lines = _4_chars_word(word, map, tingkung_code2char)
        if lines:
            for line in lines:
                words.write(line + "\n")
        lines = n_chars_word(word, map, tingkung_code2char)
        if lines:
            for line in lines:
                words.write(line + "\n")


def do_filter(combined_code):
    return (len(combined_code) >= 5
            and combined_code[:3] in tingkung_code2char
            and (combined_code[:2] not in tingkung_code2char
            or tingkung_code2char[combined_code[:2]]
                 != tingkung_code2char[combined_code[:3]])
            and converter.convert(word) not in candidates_set)

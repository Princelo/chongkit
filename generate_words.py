def single_key(code):
    keyboard = "日月金木水火土竹戈十大中一弓人心手口尸廿山女田的卜我"
    i = ord(code) - 97
    return keyboard[i]


def _2_chars_word(word, map, tingkung_code2char):
    if len(word) != 2:
        return None
    if word[0] not in map or word[1] not in map:
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
            if len(combined_code) <= 4:
                combined_code += "x"
            if combined_code[:3] in tingkung_code2char:
                if len(combined_code) == 4:
                    combined_code += "'"
                    res.append(tingkung_code2char[combined_code[:3]]
                               + single_key(combined_code[3:4]) + "\t"
                               + combined_code[:4] + "'")
                elif len(combined_code) == 5:
                    res.append(tingkung_code2char[combined_code[:3]]
                               + single_key(combined_code[3:4]) + "\t"
                               + combined_code[:4] + "'")
            res.append(word + "\t" + combined_code)
    return res


def _3_chars_word(word, map, tingkung_code2char):
    if len(word) != 3:
        return None
    if word[0] not in map or word[1] not in map or word[2] not in map:
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
                    combined_code += abbr3[0] + abbr3[-1]

                if len(combined_code) <= 4:
                    combined_code += "x"
                if combined_code[:3] in tingkung_code2char:
                    if len(combined_code) == 4:
                        combined_code += "'"
                        res.append(tingkung_code2char[combined_code[:3]]
                                   + single_key(combined_code[3:4]) + "\t"
                                   + combined_code[:4] + "'")
                    elif len(combined_code) == 5:
                        res.append(tingkung_code2char[combined_code[:3]]
                                   + single_key(combined_code[3:4]) + "\t"
                                   + combined_code[:4] + "'")
                res.append(word + "\t" + combined_code)
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

for line in essay:
    line = line[:-1]
    line = line.split("\t")
    word = line[0]
    if len(word) <= 1:
        continue
    weight = int(line[1])
    arr.append([word, weight])
arr.sort(key=lambda x: -x[1])

for item in arr:
    word = item[0]
    weight = item[1]
    if weight < 50:
        break
    lines = _2_chars_word(word, map, tingkung_code2char)
    if not lines:
        continue
    for line in lines:
        print(line)

for item in arr:
    word = item[0]
    weight = item[1]
    if weight < 200:
        break
    lines = _3_chars_word(word, map, tingkung_code2char)
    if not lines:
        continue
    for line in lines:
        print(line)

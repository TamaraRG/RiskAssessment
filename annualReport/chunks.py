import re

from annualReport import is_month, to_digit

points = {
    "liquide middelen" : 20,"vorderingen": 10,"geconsolideerde" : 20, "na voorgestelde resultaatbestemming": 20, "balans per ": 20, "vaste activa": 20,
    "voorraden" : 2,"schuld": 2,"lening": 2,"verliesrekening":2, "winst":2, "verlies":2,
    "balans":5,"schulden":5,"totaal":5,"jaarrekening" : 5,
    "agioreserve": -20, "dividenduitkering" : -80,"resultaatverdeling": -20, "groepsvermogen":-20, "verplichting":-20, "kengetallen":-80, "toelichting": -80,
    "€" : 3, "vaste":3
}

def score_all_lines(table, lines):
    len_lines = len(lines)
    score_points = []
    cache = {}
    for idx, line in enumerate(lines):
        p = 0
        line_sc = cache[idx] if idx in cache else score(table, line)
        if line_sc == 0:
            score_points.append(p)
            continue
        for t in range(idx-2, idx+2):
            if -1 > t >= len_lines: continue
            sc = cache[t] if t in cache else score(table, lines[t])
            cache[t] = sc
            if t == idx: p += sc
            else: p += int(sc * 1 / (abs(t-idx) * 2))
        score_points.append(p)
    return score_points

def score(table, text):
    points = 0
    full_score = score_subs(table, text)
    splits = re.split(r" {4,}", text)
    for item in splits:
        points += score_subs(table, item)
        if points > 100 and all([to_digit(num) is not None for num in splits[1:]]):
            points = 40
    return (full_score + points) / 2

def score_subs(table, text):
    num_points = 0
    lower_text = text.strip()
    for k,v in points.items():
        if k in lower_text: num_points += v
    if re.search(r"x *€? *1\.?000", lower_text) or re.search(r"\d\d\d", lower_text) or re.search(r"\d\d?-? ?\.?.+?-? ?\.?\d\d\d\d", lower_text): num_points += 3
    for year in ["  2022  ","  2021  ","  2020  ", "  2019  ","  2018  "]:
        if year in text or year.strip() == text: num_points += 40
    if f"totaal {table}" in lower_text: num_points += 100
    if table in lower_text: num_points += 20
    if table == lower_text or table.ljust(len(table)+3," ") in text: num_points += 100
    if table == "winst_verliesrekening":
        for txt in ["geconsolideerde winst-en-verliesrekening","winst-en-verliesrekening","staat van baten en lasten","na belastingen"]:
            if txt in lower_text: num_points += 5
            if txt == lower_text or lower_text.startswith(txt) or txt.ljust(len(txt) + 3, " ").rjust(len(txt) + 6, " ") in text: num_points += 100
    return num_points

def find_chunk(lines, score_points):
    potentials = []
    potential = [-1, -1, 0]
    zero_counter = 0
    for threshold in [100, 90]:
        for k,v in enumerate(score_points):
            if v == 0: zero_counter += 1
            else: zero_counter = 0
            p_b1 = score_points[k - 1] if k - 1 > -1 else 0
            if potential[0] == -1 and v > threshold and p_b1 < threshold:
                potential[0] = k
                potential[2] = v
                continue
            p_a1 = score_points[k + 1] if k + 1 < len(score_points) else 0
            if potential[1] == -1 and potential[0] > -1 and (v > threshold or (zero_counter > 3 and p_a1 < 25)) and (p_a1 < 25 or p_b1 < 25):
                potential[1] = k - zero_counter
                if 10 < abs(k - potential[0]) < 101 and score_points[potential[0]:k].count(0) < 20:
                    potentials.append(potential)
                elif abs(k - potential[0]) < 10 and v > threshold:
                    potential[1] = -1
                    continue
                if v > threshold: potential = [k, -1, v]
                else: potential = [-1, -1, 0]
                continue
            if potential[0] > -1: potential[2] += v
        if len(potentials) != 0: break

    if len(potentials) == 0:
        return -1, -1
    res = sorted(potentials, key=lambda x: -x[2])

    # make sure there is a date
    idx_with_date = res[0][0]
    date_idx = -1
    for idx in reversed(range(idx_with_date-5,idx_with_date+5)):
        line = lines[idx]
        if re.search(r"\d\d\D\d\d\D\d\d", line):
            date_idx = idx
            break
        for year in ["2018","2019","2020","2021","2022"]:
            if year in line:
                date_idx = idx
                break
    if -1 < date_idx < idx_with_date:
        idx_with_date = date_idx

    return idx_with_date, res[0][1]




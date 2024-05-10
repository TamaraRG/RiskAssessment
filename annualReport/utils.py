import re
from itertools import chain

months = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober",
          "november", "december"] + ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august',
                                     'september', 'october', 'november', 'december']

def index_of_smallest(l):
    if len(l) == 0: return -1
    min_idx = None
    min_val = None
    for i, item in enumerate(l):
        if min_val is None or min_val > item:
            min_idx = i
            min_val = item
    return min_idx

def clean_words(words):
    return re.sub(r'^[^a-zA-Z0-9]*', '', re.sub(r'[^a-zA-Z0-9]*$', '', words)).lower()

def is_month(text):
    for m in months:
        if m in text: return True
    return False

def is_date(text):
    if re.match(r"[0-3]?[0-9]\D\d\d\D20\d\d(?=\s|$)", text) \
            or re.match(r"[0-3]?[0-9] [^ ]* 20\d\d(?=\s|$)", text) \
            or re.match(r"[0-3]?[0-9]\D[0-1]?[0-9]\D.\d\d(?=\s|$)", text)\
            or re.match(r"20\d\d(?=\s|$)", text): return True
    if is_month(text): return True
    return False

def to_digit(text):
    if text is None: return None
    text = text.replace(".", "")
    if "," in text and "." not in text:
        text = text.replace(",", ".")
    try:
        return float(text)
    except:
        pass
    return None

def dates_count(line):
    date_count = 0
    date_count = max(date_count, len(re.findall(r"[0-3]?[0-9]\D\d?\d\D20\d\d(?=\s|$)", line)))
    if date_count > 0: return date_count
    month_str = '|'.join(months)
    date_count = max(date_count, len(re.findall(f"[0-3]?[0-9] ({month_str}) 20\\d\\d(?=\\s|$)", line)))
    if date_count > 0: return date_count
    date_count = max(date_count, len(re.findall(r"[0-3]?[0-9]\D[0-1]?[0-9]\D.\d\d(?=\s|$)", line)))
    if date_count > 0: return date_count
    date_count = max(date_count, len(re.findall(r"  20\d\d(?=\s|$)", line)))
    return date_count

def to_special(word):
    if is_date(word): return "<date>"
    if to_digit(word) is not None: return "<real>"
    return clean_words(word)

def is_in_words(word, dword):
    if dword == word: return True
    if dword in word: return True
    if dword in word.split(' '): return True
    word = f" {word} "
    if dword in word: return True
    if word in dword: return True
    return False

def extract_results(line):
    m = re.search(r"(.*)=(\d+):(\d+);(\d+)", line)
    name = m.group(1)
    start = int(m.group(2)) - 1
    end = int(m.group(3)) - 1
    date = int(m.group(4)) - 1
    return name, start, end, date

def get_score_lines(lines, idx, d):
    scores = 0
    dist = len(lines[idx:])
    to_many_words = 0
    for i, line in enumerate(lines):
        if len(line) < 2: continue
        score_line = 0
        all_words = [to_special(w) for w in re.split(r" {1,}", line) if len(to_special(w)) > 2]
        if len(all_words) > 15: return 0
        if len(all_words) > 9: to_many_words += 1
        for word in [clean_words(w) for w in re.split(r" {2,}", line)]:
            if len(word) < 4: continue
            if word in d: points = [d[word] * 2]
            else: points = [v * 2 if word == k else v for k, v in d.items() if is_in_words(word, k)]
            if len([p for p in points if p < -99]) > 0: return 0
            score_line += sum(points)
        for word in all_words:
            if word in d: points = [d[word]]
            else: points = [v * (1 if v > 2 else 0) for k, v in d.items() if word in k]
            score_line += sum(points)
        if i == idx: scores += score_line
        else: scores += int(((dist - abs(i - idx)) / dist) * score_line)
    if to_many_words > 4:
        print("TO MANY WORDS!")
        return 0
    return max(0, scores)

def get_page_bounds(row_idx, all_lines):
    start_idx = row_idx
    start_page = all_lines[start_idx]
    while "" not in start_page and start_idx > 0:
        start_page = all_lines[start_idx]
        start_idx -= 1

    end_idx = row_idx+1
    end_page = all_lines[end_idx]
    while "" not in end_page and end_idx < len(all_lines):
        end_page = all_lines[end_idx]
        end_idx += 1
    return start_idx, end_idx

def multi_colmn_page(row_idx, all_lines):
    start_idx, end_idx = get_page_bounds(row_idx, all_lines)
    page = all_lines[start_idx:end_idx]
    max_line_len = max([len(line) for line in page])
    spaces = [0 for i in range(0,max_line_len)]
    for line in page:
        for idx, c in enumerate(line):
            if c != " ": spaces[idx] += 1
    mid = int(max_line_len/2)
    min_idx = index_of_smallest(spaces[mid-5:mid+5])
    min_idx = mid+(min_idx-5)
    middle = spaces[min_idx]
    if middle < 2: return min_idx, start_idx, end_idx
    return 0, start_idx, end_idx

def find_dates(all_lines,name):
    date_indexes = []
    is_found = False
    for idx, line in enumerate(all_lines):
        split_words = [to_special(w) for w in re.split(r" {1,}", line)]
        date_words = split_words.count('<date>')
        date_count = dates_count(line)
        if date_count > 1 and date_words > 1 and len(split_words) < 10:
            if any([skip in line for skip in  ["vennootschap","beloningsverhoudingen","dienstverband", "verdiende","in kg"]]): continue
            if line.strip().startswith(name): return [idx]
            if name == "winst" and (any([sort in line for sort in ["activa", "passiva"]]) or re.findall(r"  20\d\d(?=\s|$)", line) == 0): continue
            if "noot" in line:
                if not is_found: date_indexes = []
                date_indexes.append(idx)
                is_found = True
                continue
            if "baten" in line and name == "winst":
                if not is_found: date_indexes = []
                date_indexes.append(idx)
                is_found = True
                continue
            if is_found: continue
            date_years = len(re.findall(r"  20\d\d(?=\s|$)", line))
            if (date_years > 0 or "omschrijving" in line) and name in ["activa","passiva"]:continue
            date_indexes.append(idx)
    return date_indexes


def calc_all_score(all_lines, dates_idx,  dicts, leve_one=True, sub_idx=4, add_idx=20):
    all_scores = []
    for idx, line in enumerate(all_lines):
        if leve_one and idx not in dates_idx: continue
        split_words = [to_special(w) for w in re.split(r" {1,}", line)]
        date_words = split_words.count('<date>')
        date_count = dates_count(line)
        if leve_one and date_count in [4, 6]:
            middle_idx, start_idx, end_idx  = multi_colmn_page(idx, all_lines)
            if middle_idx == 0:
                all_scores.append(date_words + date_count)
                continue
            first_part = [l[:middle_idx] for l in all_lines[idx-sub_idx:idx+add_idx]]
            sec_part = [l[middle_idx:] for l in all_lines[idx-sub_idx:idx+add_idx]]
            first_scores = sum(calc_all_score(first_part, 4, dicts, False, sub_idx, add_idx))
            sec_scores = sum(calc_all_score(sec_part, 4, dicts, False, sub_idx, add_idx))
            all_scores.append(max(first_scores, sec_scores))
        elif date_count in [2, 3] and date_words > 1 and len(split_words) < 10:
            lines_score = get_score_lines(all_lines[idx-sub_idx:idx+add_idx], 4, dicts)
            all_scores.append(date_words + date_count + lines_score)
        else: all_scores.append(0)
    return all_scores


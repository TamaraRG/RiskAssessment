import re

months = ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober",
          "november", "december"] + ['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august',
                                     'september', 'october', 'november', 'december']

def is_month(text):
    for m in months:
        if m in text: return True
    return False

def is_date(text):
    if re.match(r"[1-3]\d\D[0-1]?\d\D20\d\d", text) \
            or re.match(r"[1-3]\d.*20\d\d", text) \
            or re.match(r"[1-3]\d\D[0-1]?\d\D\d\d$", text): return True
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


def trim_list_start_and_end(l: list):
    while len(l) > 0 and l[0] is None: l.pop(0)
    while len(l) > 0 and l[len(l) - 1] is None: l.pop(len(l) - 1)

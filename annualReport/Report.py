import re
from hashlib import sha256

from BaseReport import BaseReport
from annualReport import to_digit, is_month, chunks


class Report(BaseReport):

    def __init__(self, filename_pdf: str, db_path: str, klantnr: str, is_picture_mode=0, write_to_db=True):
        super().__init__(filename_pdf, db_path, klantnr, is_picture_mode, write_to_db)
        if self.write_to_db:
            self.cur.execute(f'CREATE TABLE IF NOT EXISTS "activa" (id TEXT primary key, klantnr TEXT, key TEXT, cat TEXT, bedrag REAL, datum DATE, geconsolideerde BOOL)')
            self.cur.execute(f'CREATE TABLE IF NOT EXISTS "passiva" (id TEXT primary key, klantnr TEXT, key TEXT, cat TEXT, bedrag REAL, datum DATE, geconsolideerde BOOL)')
            self.cur.execute(f'CREATE TABLE IF NOT EXISTS "winst_verliesrekening" (id TEXT primary key, klantnr TEXT, key TEXT, cat TEXT, bedrag REAL, datum DATE, geconsolideerde BOOL)')
        else:
            with open("./tmp/test.txt","w") as f:
                for line in self.lines:
                    f.write(f"{line}\n")
        for i, line in enumerate(self.lines):
            self.lines[i] = line.lower()

    def calculate_positions(self, table, parts):
        test = [0] * max([len(part) for part in parts])
        date_idx = -1
        for t in range(0, 10): test[t] = 10
        for ix, part in enumerate(parts):
            if " " in part: continue
            if table == "winst_verliesrekening" and "begroting" in part:
                date_idx = ix
                continue
            for i, c in enumerate(part):
                if c.isalnum(): test[i] += 1
        c = test[-1]
        i = len(test)-1
        while c < 2:
            test[i] = 10
            i -= 1
            c = test[i]
        total_str = ''.join(['#' if num > 0 else ' ' for num in test])
        idx = [0] + [item.start(0) for item in re.finditer(r" {3,}", total_str)] + [len(total_str)-1]
        if date_idx > -1:
            clean_date = [item for item in re.split(r" {3,}", parts[date_idx].replace("begroting", "  KILL").replace("realisatie", "   "))]
            try:
                parts[date_idx] = "".join([clean_date[i-1].rjust(idx[i]-idx[i-1]) for i in range(1, len(idx))])
            except Exception as ex: print(ex)
        tmp2 = [[("" if i == 1 else 0), idx[i-1], idx[i]] for i in range(1, len(idx))]
        return tmp2

    def find_cat(self, rest_list):
        for item in rest_list:
            if all([v is None for v in item[1:]]):
                return item[0]
        return None

    def find_dates(self, table_list):
        dates = []
        date_idx = -1
        for i, item in enumerate(table_list):
            if all([v is None for v in item]): continue
            if (any([re.search(r"\d?\d?-? ?\.?.*-? ?\.?\d\d\d\d", str(text)) for text in item[1:]]) or any([re.search(r"\d\d\.?\d\d\.?\d\d", str(text)) for text in item[1:]])):
                dates = ['dates'] + [None if d and "KILL" in d else d for d in item[1:]]
                date_idx = i
                break
            if any([is_month(str(text)) for text in item[1:]]):
                date_times = item[1:]
                if i > 0 and not all([re.search(r"20\d\d", str(text)) for text in item[1:]]) and all(
                        [re.search(r"20\d\d", str(text)) for text in table_list[i - 1][1:]]):
                    date_times = [f"{y} {table_list[i - 1][v + 1]}" for v, y in enumerate(date_times)]
                dates = ['dates'] + date_times
                date_idx = i
                break
        return date_idx, dates

    def fix_digit_list(self, res_digits):
        date_idx, dates = self.find_dates(res_digits)
        if date_idx == -1: return None, None
        res_digits = [[el for idx, el in enumerate(rd) if idx == 0 or dates[idx] is not None] for rd in res_digits]
        dates = [el for idx,el in enumerate(dates) if idx == 0 or el is not None]
        items = []
        for i, item in enumerate(res_digits):
            if all([v is None for v in item]) or date_idx == i: continue
            if i > 0 and res_digits[i-1][0] is None and item[0] is not None and all([numbers is not None for numbers in res_digits[i-1][1:]]) and all([numbers is None for numbers in item[1:]]):
                item = [item[0]] + res_digits[i-1][1:]
            if item[0] is None or all([numbers is None for numbers in item[1:]]) or all([to_digit(i) is None for i in item[1:]]): continue
            item[0] = (item[0], self.find_cat(res_digits[i:]) or item[0])
            if not (len(dates) > 0 and dates[1:] == item[1:]):
                items.append(item)
        return items, dates

    def read_entries(self, parts, pos):
        res_digits = []
        for part in parts:
            item = [part[p[1]:p[2]+1].strip() for p in pos]
            res_digits.insert(0,[p if p != '' else None for p in item])
        return self.fix_digit_list(res_digits)

    def read_chunk(self, table, parts):
        pos = self.calculate_positions(table, parts)
        if pos is None: return None, None
        all_items, dates = self.read_entries(parts, pos)
        if dates is None:
            print("Dates not found!")
            return None, None
        print(all_items, dates)
        geconsoli = any(["geconsoli" in p for p in parts])
        entries = []
        for item in all_items:
            item_name = item[0][0]
            cat = item[0][1]
            if item_name.startswith("totaal"): continue
            for idx, entry in enumerate(item[1:]):
                date = dates[idx+1]
                item_id = sha256(f'{self.klantnr}{item_name}{date}'.encode('utf-8')).hexdigest()
                entries.append((item_id,self.klantnr,item_name, cat, to_digit(entry) or 0, date, geconsoli))
        if self.write_to_db:
            self.cur.executemany(f"INSERT OR REPLACE INTO {table} VALUES (?,?,?,?,?,?,?)", entries)
        return all_items, dates

    def vertical_chunk(self, table, min_idx, max_idx):
        lower_text = self.lines[min_idx]
        keywords = [table] + ["geconsolideerde winst-en-verliesrekening", "winst-en-verliesrekening", "staat van baten en lasten"]
        for keyword in keywords:
            try:
                idx = lower_text.index(keyword)
                if idx < 15: break
                else: return [line[idx-3:] for line in self.lines[min_idx:max_idx+1] if line.strip() != '']
            except: pass
        return [line for line in self.lines[min_idx:max_idx+1] if line.strip() != '']

    def scan_for_chunk(self, table):
        point_list = chunks.score_all_lines(table, self.lines)
        min_idx, max_idx = chunks.find_chunk(self.lines, point_list)
        if min_idx == -1 or max_idx == -1: return None
        print(f"{table} chunk at {min_idx+1}-{max_idx+1}")
        return self.vertical_chunk(table, min_idx, max_idx)

    def parse(self):
        tables = ['activa','passiva','winst_verliesrekening']
        for table in tables:
            print("-" * 100)
            chunk = self.scan_for_chunk(table)
            if not chunk:
                print(f"No chunk found for {table}")
                continue
            self.read_chunk(table, chunk)
        print("-" * 100)

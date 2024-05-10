import re

from invoice2data.input import pdftotext,tesseract

from BaseReport import BaseReport


class Report(BaseReport):

    def __init__(self, filename_pdf: str, db_path: str, klantnr: str, is_picture_mode=0,write_to_db=True):
        super().__init__(filename_pdf, db_path, klantnr, is_picture_mode, write_to_db)

        #with open(f"./tmp/{klantnr}.txt", "w") as f:
        #    if is_picture_mode == 1: f.write(tesseract.to_text(filename_pdf).decode("utf-8"))
        #    else: f.write(pdftotext.to_text(filename_pdf).decode("utf-8"))

        self.cur.execute(f'CREATE TABLE IF NOT EXISTS "sbicode" (id TEXT primary key, sbi text, klantnr TEXT, description TEXT)')
        self.cur.execute(f'CREATE TABLE IF NOT EXISTS "kvk" (id TEXT primary key, klantnr TEXT, rechtsvorm TEXT, mdw text)')

    def parse(self):
        mdw = 0
        rechtsvorm = None
        for line in self.lines:
            if "Activiteiten (SBI)".lower() in line.lower():
                m = re.search("Activiteiten \\(SBI\\) *([\\d]+) *- *(.*)", line, re.IGNORECASE)
                if not m: continue
                code = m.group(1)
                desc = m.group(2)
                id = self.klantnr + "-" + code
                desc = self.find_sbi(code) or desc
                self.cur.execute(f'INSERT OR REPLACE INTO "sbicode" VALUES (?,?,?,?)', (id, code, self.klantnr, desc))
            if "-code" in line.lower():
                m = re.search("...-code: ([\\d]+) *- *(.*)", line, re.IGNORECASE)
                if not m: continue
                code = m.group(1)
                desc = m.group(2)
                desc = self.find_sbi(code) or desc
                id = self.klantnr + "-" + code
                self.cur.execute(f'INSERT OR REPLACE INTO "sbicode" VALUES (?,?,?,?)', (id, code, self.klantnr, desc))
            if "kvk-nummer" in line.lower() and "ingeschreven" not in line.lower():
                m = re.search("KvK-nummer *([\\d]+)", line, re.IGNORECASE)
                if not m: continue
                kvknr = m.group(1)
            if rechtsvorm is None and "rechtsvorm " in line.lower():
                m = re.search("Rechtsvorm *(.*)", line, re.IGNORECASE)
                if not m: continue
                rechtsvorm = m.group(1)
            if "werkzame personen" in line.lower():
                m = re.search("Werkzame personen *([\\d]+)", line, re.IGNORECASE)
                if not m: continue
                mdw = m.group(1)

        try:
            self.cur.execute(f'INSERT OR REPLACE INTO "kvk" VALUES (?,?,?,?)', (kvknr, self.klantnr, rechtsvorm, mdw))
        except Exception as ex:
            print(ex)

    def find_sbi(self, sbi_code):
        with open("../data/Standaard_Bedrijfsindeling_2008_tcm109-510165.csv", encoding="ISO-8859-1") as file:
            for row in file:
                if sbi_code in row:
                    return ",".join(row.split(",")[1:]).strip()
            return None

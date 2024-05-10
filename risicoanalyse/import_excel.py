import openpyxl
from BaseReport import BaseReport


class Excelreport(BaseReport):

    def __init__(self, filename_xlsx: str, db_path: str, klantnr: str):
        super().__init__(filename_xlsx, db_path, klantnr)

        self.cur.execute(f'CREATE TABLE IF NOT EXISTS "materialiteit" (id text primary key, klantnr TEXT, Boekjaar int, Materialiteit int, UM int, TA int)')
        self.cur.execute(f'CREATE TABLE IF NOT EXISTS "risico" (id TEXT primary key, klantnr TEXT, account TEXT, bewering Text, bedrag text, post_boven_UM text, materiele_afwijking text, frauderisico text, complexiteit text, inherent_risico text, beheersingsmaatregel_aanwezig text, beheersingsmaatregel_testen text, conclusie text  )')

    def parse(self):

        wb = openpyxl.load_workbook(self.filename, data_only=True, read_only=True)
        try:
            ws = wb["Risico analyse planningsfase"]
        except:
            ws = wb.worksheets[0]

        materialiteit = []
        m = {"klantnr": self.klantnr}
        risico = []


        for row in ws.rows:
            for cell in row:
                if cell.value is None: continue
                if cell.value == "Boekjaar":
                    materialiteit.append([c.value for c in row if c.value is not None])
                if cell.value == "Materialiteit":
                    materialiteit.append([c.value for c in row if c.value is not None])
                if cell.value == "Uitvoeringsmaterialiteit":
                    materialiteit.append([c.value for c in row if c.value is not None])
                if cell.value == "Triviale afwijking":
                    materialiteit.append([c.value for c in row if c.value is not None])

        for k in materialiteit:
            m[k[0]] = k[1]

        id = self.klantnr + "-" + str(m["Boekjaar"])
        self.cur.execute(f'INSERT OR REPLACE INTO "materialiteit" VALUES (?,?,?,?,?,?)', (id, self.klantnr, m["Boekjaar"], m["Materialiteit"], m["Uitvoeringsmaterialiteit"], m["Triviale afwijking"]))


        found = False
        for row in ws.rows:
            if not found:
                for cell in row:
                    if cell.value is None: continue
                    if "Geen nadere toelichting opnemen" in str(cell.value):
                        found = True
            else:
                if any(["FORMULE REGEL" in str(cell.value) for cell in row]): continue
                v = [row[1].value,row[2].value,row[4].value] + [y.value for y in row[6:13]] + [row[14].value]
                if len(v) > 0 and any(v):
                    risico.append(v)

        for i in risico:
            tmp = i[1] or ""
            id = f"{self.klantnr}-{i[0]}-{tmp}"
            self.cur.execute(f'INSERT OR REPLACE INTO "risico" VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)', (id, self.klantnr, i[0], i[1], i[2], i[3], i[4], i[5], i[6], i[7], i[8], i[9], i[10]))
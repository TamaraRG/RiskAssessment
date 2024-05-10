import csv, sqlite3, re
import os

FILE = "../data/81156ned_UntypedDataSet_11102023_160238.csv"
FILE_META = "../data/81156ned_metadata.csv"
FILES_AEX = "../data/FD"
PATH = "../tmp/test.db3"

conn = sqlite3.connect(PATH)
cur = conn.cursor()

#Investeringsverwachtingen in CBS
l = []
header =[]

with open(FILE, 'r') as file:
    rows = csv.reader(file, delimiter=';', quotechar='"')
    old_row = None
    for idx, row in enumerate(rows):
        if idx == 0:
            header = row
            continue
        row = [r.replace('.','0').strip() if isinstance(r, str) else r for r in row]
        if old_row is not None and old_row[1] == row[1] and int(old_row[2])+1 == int(row[2]):
                v = round((float(row[4]) - float(old_row[4])) / (float(old_row[4])+0.001) * 100, 2)
                row = row + [v]
        else: row = row + [None]
        l.append(row)
        old_row = row

col_names = ','.join([f'{col} text primary key' if idx == 0 else f'{col} text' for idx, col in enumerate(header)]) +', Revenue_growth text'
#print(col_names)
cur.execute(f'Create table if not exists CBS_invest ({col_names})')
conn.commit()

cols = ','.join([f'{col}' for col in header]) + ',Revenue_growth'
cols_q = ','.join((len(header)+1)*'?')

cur.executemany(f'INSERT OR REPLACE INTO CBS_invest ({cols}) VALUES ({cols_q})', l)
conn.commit()

#METADATA investeringsverwachtingen in CBS
meta_list = []
meta_header = []

with open(FILE_META, 'r') as meta:
    meta_rows = csv.reader(meta, delimiter=';', quotechar='"')
    for meta_idx, meta_row in enumerate(meta_rows):
        if meta_idx == 0:
            meta_header = meta_row[0:2]
            continue
        m = re.search(r"([\d, \-\+]+)", meta_row[1])
        if m: meta_list.append([meta_row[0], m.group(1)])

meta_names = ','.join(f'{m_row} text primary key' if meta_idex == 0 else f'{m_row} text' for meta_idex, m_row in enumerate(meta_header))
meta_cols = ','.join(f'{meta_col}' for meta_col in meta_header)
meta_q = ','.join((len(meta_header))*'?')

cur.execute(f'Create table if not exists CBS_meta({meta_names})')
conn.commit()
#cur.executemany(f'INSERT OR REPLACE INTO CBS_meta({meta_cols}) VALUES ({meta_q})', meta_list)
#conn.commit()
cur.execute(f'Update CBS_invest SET BedrijfstakkenbranchesSBI2008 = m.Title FROM CBS_meta as m WHERE m.Keys = CBS_invest.BedrijfstakkenbranchesSBI2008')
conn.commit()


#Beursontwikkeling in FD
for f in os.listdir(FILES_AEX):
    if f.startswith("."):
        continue
    with open(os.path.join(FILES_AEX,f), 'r') as file_AEX:
        rows_AEX = [r for r in csv.reader(file_AEX, delimiter=';')]
        for idx, row_AEX in enumerate(rows_AEX):
            for i, cell_AEX in enumerate(row_AEX):
                row_AEX[i] = cell_AEX.replace(',','.')
            if idx == 1:
                rows_AEX[idx] = row_AEX + [0] + [None]
            elif idx > 1:
                rows_AEX[idx] = row_AEX + [round((float(rows_AEX[idx-1][5])-float(row_AEX[5]))/float(row_AEX[5])*100,2)]+ [None]

col_AEX = ','.join([f'{c} text primary key' if index == 0 else f'{c} text' for index, c in enumerate(rows_AEX[0])])+', Growth text'+', Boekjaar text'
cur.execute(f'Create table if not exists FD_beurs ({col_AEX})')
conn.commit()

cols_AEX = ','.join([f'{c}' for c in rows_AEX[0]]) +', Growth'+', Boekjaar'
cols_AEX_q = ','.join(len(rows_AEX[0])*'?')+',?'+',?'
lines_AEX = rows_AEX[1:]

cur.executemany(f'INSERT OR REPLACE INTO FD_beurs ({cols_AEX})VALUES ({cols_AEX_q})', lines_AEX)
conn.commit()
cur.execute(f'Update FD_beurs SET Boekjaar = substr(Datum,length(Datum)-3,4)')
conn.commit()
conn.close()

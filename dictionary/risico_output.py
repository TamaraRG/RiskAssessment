import re
import sqlite3

con = sqlite3.connect("../tmp/test.db3")
cur = con.cursor()
cur.execute('ATTACH DATABASE "../dict.db3" AS dicty')

with open('../Create_inputdata', 'r') as file:
    cur.execute(file.read())
    con.commit()

rf_dict = {'complexiteit':False,'subjectiviteit':False,'correcties': False, 'onzekerheid':False,'frauderisico':False,'materiele_afwijking':False,'gebrek_uniformiteit':False, 'inherent_risico':False}
#Significant fraud risk weggelaten i.v.m. risk factor = fraud is altijd 100%.
NL_risk_dict = {'Niet in scope':0, 'Laag':1, 'RAMB':2,'Significant risico':3}
#EN_risk_dict = {1:'Out_of_scope', 2:'Low', 3:'RAMB', 4:'Significant'}
bw_dict = {'bestaan': False, 'voorkomen': False, 'volledigheid': False, 'nauwkeurigheid':False, 'waardering':False, 'afgrenzing':False, 'classificatie':False, 'presentatie':False, 'rechten en verplichtingen':False}

def check_dict(oms):
    oms = oms.strip()
    cur.execute("SELECT COALESCE(keyoverride,id) FROM dicty.dict WHERE instr(?,oms) > 0 order by instr(oms,?) desc, instr(?,oms) desc limit 1", (oms,oms,oms))
    res = cur.fetchone()
    if res is None or len(res) == 0:
        cur.execute("INSERT INTO dicty.dict (oms) VALUES (?)", (oms,))
        cur.execute("SELECT COALESCE(keyoverride,id) FROM dicty.dict WHERE instr(?,oms) > 0 order by instr(oms,?) desc, instr(?,oms) desc limit 1", (oms,oms,oms))
        res = cur.fetchone()
    return res[0]

def check_subcat_dict(oms):
    oms = oms.strip()
    cur.execute("SELECT subcat FROM dicty.dict WHERE instr(?,oms) > 0 order by instr(oms,?) desc, instr(?,oms) desc limit 1",(oms, oms, oms))
    res = cur.fetchone()
    return res[0]

def extract_risico():
    cur.execute("SELECT klantnr, account, bewering, conclusie, bedrag FROM risico")
    IR = cur.fetchall()

    for row in IR:
        found = [r for r in row]
        if row[3] is None: continue
        found3 = False
        for key, val in NL_risk_dict.items():
            if key.lower() in row[3].lower():
                found[3] = val
                found3 = True
                break
        if not found3:
            print("NO CONCLUSION:",row[3].lower())
            continue
        found[1] = check_dict(row[1].lower())
        subcat = check_subcat_dict(row[1].lower())

        bw_key = str(found[2]).lower()
        item = bw_dict.copy()
        for k in bw_dict.keys():
            item[k] = k in bw_key
        cols = [(f"r_{q.replace(' ','_')}",w) for q,w in item.items()]
        id = f"{row[0]}2021{found[1]}"
        res_data = (id, row[0], 2021) + tuple([p[1] for p in cols]) + (found[1],row[4],found[3])
        query = f"INSERT OR IGNORE INTO inputdata (a_id, a_klantnr, a_boekjaar,{','.join([p[0] for p in cols])}, j_account, j_bedrag, o_conclusie) VALUES({','.join(['?' for i in range(0,len(res_data))])})"
        cur.execute(query, res_data)
        bw_set = ','.join([f'{p[0]}={1 if p[1] else 0}' for p in cols])
        j_bedrag = 0
        try: j_bedrag = float(row[4])
        except: pass
        query = f"update inputdata SET {bw_set}, j_bedrag={j_bedrag}, o_conclusie={found[3]}, j_subcat={subcat or 'NULL'} WHERE j_account=? AND a_klantnr=?"
        cur.execute(query,(found[1], row[0]))

def extract_rechtsvormen():
    cur.execute("SELECT klantnr, rechtsvorm, mdw FROM kvk")
    RV = cur.fetchall()

    for row in RV:
        val = check_dict(row[1].lower())
        query = "UPDATE inputdata SET k_rechtsvorm=?, k_mdw=? WHERE a_klantnr=?"
        cur.execute(query, (val, row[2], row[0]))

def extract_risk_factors():
    cur.execute("SELECT name FROM PRAGMA_table_info('risico')")
    col_name = cur.fetchall()
    l = []
    for c in col_name:
        if c[0] in rf_dict: l.append(c[0])

    cur.execute(f'SELECT {",".join(l)}, klantnr, account FROM risico')
    RF = cur.fetchall()

    for r in RF:
        if r[-1] is None: continue
        account = check_dict(r[-1].lower())
        row = [i and i.strip().lower() == 'ja' for i in r][:-2]
        setlist = []
        for c, k in enumerate(l):
            setlist.append(f"r_{k}={1 if row[c] else 0}")

        query = f"UPDATE inputdata SET {','.join(setlist)}, r_gebrek_uniformiteit=0,r_subjectiviteit=0,r_correcties=0, r_onzekerheid=0 WHERE a_klantnr=? AND j_account=?"
        cur.execute(query, (r[-2], account))

def extract_materialiteit():
    cur.execute("SELECT Materialiteit, UM, TA, klantnr FROM materialiteit")
    rows = cur.fetchall()
    for row in rows:
        query = "UPDATE inputdata SET m_M=?, m_UM=?, m_TA=? WHERE a_klantnr=?"
        cur.execute(query, row)


def extract_sbi():
    cur.execute("SELECT sbi, klantnr from sbicode order by klantnr")
    rows = cur.fetchall()
    old_klantnr = -1
    sbi = 1
    for row in rows:
        if old_klantnr == row[1]: sbi += 1
        else: sbi = 1
        query = f"UPDATE inputdata SET k_sbi{sbi}=? WHERE a_klantnr=?"
        cur.execute(query, row)
        old_klantnr = row[1]

def extract_jrk():
    for table in ["activa", "passiva","winst_verliesrekening"]:
        cur.execute(f"SELECT klantnr, key, cat, bedrag, datum, geconsolideerde from {table} order by klantnr")
        rows = cur.fetchall()
        for row in rows:
            try:
                klantnr = row[0]
                bedrag = row[3]
                date = str(row[4])
                if re.search(r"\d\d\D\d\d\D\d\d$", date):
                    row[4] = date[:6] + '20' + date[6:]
                boekjaar = int(date[-4:]) + 1
                geconsolideerd = row[5]
                waarderingsgrondslag = 0
                schatting = 0
                account = check_dict(row[1])
                subcat = check_dict(row[2])
                query = f"UPDATE inputdata SET j_subcat=?, j_bedrag=?, j_geconsolideerd=?, j_waarderingsgrondslag=?, j_schatting=? WHERE a_klantnr=? AND a_boekjaar=? AND j_account=?"
                cur.execute(query, (subcat, bedrag, geconsolideerd, waarderingsgrondslag, schatting, klantnr, boekjaar, account))
            except Exception as ex:
                print(row)

def extract_AEX():
    dict = {}
    cur.execute("Select Boekjaar, sum(Growth) FROM FD_beurs Group by Boekjaar")
    AEX_growth = cur.fetchall()
    for row in AEX_growth:
        dict[row[0]] = row[1]
    cur.executemany("UPDATE inputdata SET c_beursontwikkeling = ? WHERE a_boekjaar = ?",[(v, k) for k,v in dict.items()])


def extract_CBS():
    cur.execute(f'UPDATE inputdata SET c_investeringsverw = cbs.Revenue_growth from CBS_invest as cbs WHERE cbs.Perioden = inputdata.a_boekjaar and trim(cbs.BedrijfstakkenbranchesSBI2008) = inputdata.k_sbi1 and inputdata.c_investeringsverw is Null')
    con.commit()
    cur.execute(f'UPDATE inputdata SET c_investeringsverw = cbs.Revenue_growth from CBS_invest as cbs WHERE cbs.Perioden = inputdata.a_boekjaar and cast(trim(cbs.BedrijfstakkenbranchesSBI2008) as int) = substr(k_sbi1,1,4) and inputdata.c_investeringsverw is Null')
    con.commit()
    cur.execute(f'UPDATE inputdata SET c_investeringsverw = cbs.Revenue_growth from CBS_invest as cbs WHERE cbs.Perioden = inputdata.a_boekjaar and cast(trim(cbs.BedrijfstakkenbranchesSBI2008) as int) = substr(k_sbi1,1,3) and inputdata.c_investeringsverw is Null')
    con.commit()
    cur.execute(f'UPDATE inputdata SET c_investeringsverw = cbs.Revenue_growth from CBS_invest as cbs WHERE cbs.Perioden = inputdata.a_boekjaar and cast(trim(cbs.BedrijfstakkenbranchesSBI2008) as int) = substr(k_sbi1,1,2)  and inputdata.c_investeringsverw is Null')
    con.commit()
    cur.execute(f'UPDATE inputdata SET c_investeringsverw = cbs.Revenue_growth from CBS_invest as cbs WHERE cbs.Perioden = inputdata.a_boekjaar and cast(trim(cbs.BedrijfstakkenbranchesSBI2008) as int) = substr(k_sbi1,1,1)  and inputdata.c_investeringsverw is Null')
    con.commit()



extract_risico()
extract_rechtsvormen()
extract_risk_factors()
extract_materialiteit()
extract_sbi()
extract_jrk()
extract_CBS()
extract_AEX()
con.commit()
con.close()
print("All done!")

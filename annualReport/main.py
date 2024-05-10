import os, re, sqlite3, pdf2txt

from utils import to_special, dates_count, get_score_lines, extract_results, multi_colmn_page, calc_all_score, \
	find_dates

con = sqlite3.connect("chunk_dict.db3")
cur = con.cursor()
cur.execute('CREATE TABLE IF NOT EXISTS "dict" (id TEXT PRIMARY KEY, word TEXT, sort TEXT, score INTEGER NOT NULL)')
con.commit()

IGNORE = ['naar', 'voor', 'zijn', 'alle', 'worden', 'niet']
pdfs = [each for each in os.listdir("pdf") if each.lower().endswith('.pdf')]
insert_dict = {}

def score_words_chunk(chunk_lines):
	max_word_count = 0
	dict_words = {}
	for cl in chunk_lines:
		split_words = [to_special(w) for w in re.split(r" {2,}", cl) if len(to_special(w)) > 2]
		if len(split_words) == 0: continue
		max_word_count = max(max_word_count, len(split_words))
		for clean_word in split_words:
			if clean_word.startswith('<'): continue
			if clean_word is None or len(clean_word) < 4 or clean_word in IGNORE: continue
			if clean_word not in dict_words: dict_words[clean_word] = 0
			dict_words[clean_word] += 1
	return dict_words, max_word_count

def create_dict(res_all_lines, all_lines):
	insert_list = []
	insert_neg_list = []
	max_line_count = 0
	all_names = []
	for line in res_all_lines:
		name, start, end, date = extract_results(line)
		all_names.append(name)
	for line in res_all_lines:
		name, start, end, date = extract_results(line)
		max_line_count = max(max_line_count, end-start)
		chunk_lines = all_lines[start:end]
		dict_words, max_word_count = score_words_chunk(chunk_lines)
		for word, score in dict_words.items():
			key = f"{name}|{word}"
			if key not in insert_dict: insert_dict[key] = 1
			else: insert_dict[key] += 1
			insert_list.append((key, word, name, insert_dict[key]))
		for neg_name in all_names:
			if neg_name == name: continue
			for sentence, score in dict_words.items():
				all_words = [to_special(w) for w in re.split(r" {1,}", sentence) if len(to_special(w)) > 2 and "<" not in to_special(w)]
				if len(all_words) < 6:
					key = f"{neg_name}|{sentence}"
					if key not in insert_dict: insert_dict[key] = -1
					else: insert_dict[key] -= 1
					insert_neg_list.append((f"{neg_name}|{sentence}", sentence, neg_name, insert_dict[key]))

	cur.executemany("INSERT OR REPLACE INTO dict (id, word, sort, score) VALUES (?,?,?,?)", insert_neg_list)
	cur.executemany("INSERT OR REPLACE INTO dict (id, word, sort, score) VALUES (?,?,?,?)", insert_list)
	print(f"max_word_count: {max_word_count} max_line_count:{max_line_count}")

def create_neg_dict(res):
	insert_list = []
	for name, tot_score, start, end, date_idx in res:
		for idx, score in tot_score.items():
			if date_idx == idx: continue
			ch = all_lines[idx-4:idx+20]
			dict_words, max_word_count = score_words_chunk(ch)
			for word, score in dict_words.items():
				all_words = [to_special(w) for w in re.split(r" {1,}", word) if len(to_special(w)) > 2 and "<" not in to_special(w)]
				if len(all_words) < 6:
					key = f"{name}|{word}"
					if key not in insert_dict: insert_dict[key] = -1
					else: insert_dict[key] -= 1
					insert_list.append((f"{name}|{word}", word, name, insert_dict[key]))

	cur.executemany("INSERT OR IGNORE INTO dict (id, word, sort, score) VALUES (?,?,?,?)", insert_list)

for pdf in pdfs:
	pdf_file = os.path.join("pdf", pdf)
	txt_file = os.path.join("pdf", pdf.lower().replace(".pdf", ".txt"))
	res_file = os.path.join("pdf", pdf.lower().replace(".pdf", ".res"))

	if not os.path.exists(res_file):
		with open(res_file, "w") as res: res.write("activa=0:0;0\npassiva=0:0;0\nwinst=0:0;0\n")

	with open(res_file, 'r') as res: res_all_lines = res.readlines()

	with open(txt_file, "w") as f:
		txt = pdf2txt.to_text(pdf_file)
		f.write(txt)
	all_lines = [l.lower() for l in txt.split('\n')]

	#create_dict(res_all_lines, all_lines)

	dicts = {}
	cur.execute("SELECT sort, word, score from dict order by score")
	dict_all = cur.fetchall()
	for row in dict_all:
		if row[0] not in dicts: dicts[row[0]] = {}
		dicts[row[0]][row[1]] = row[2]

	res = []
	for line in res_all_lines:
		name, start, end, date_idx = extract_results(line)
		all_dates = find_dates(all_lines, name)
		all_scores = calc_all_score(all_lines, all_dates, dicts[name], True, 4, 20)
		if max(all_scores) < 5:
			all_scores = calc_all_score(all_lines, all_dates, {k: v for k, v in dicts[name].items() if v > 0}, True, 4, 50)
		#for idx, dt in enumerate(all_dates):
		#	if date_idx == dt:
		#		print(pdf, name, dt, all_scores[idx])
		res.append((name, {all_dates[i]: s for i, s in enumerate(all_scores)}, start, end, date_idx))

	#create_neg_dict(res)

	for name, tot_score, start, end, date_idx in res:
		if date_idx not in tot_score:
			print("No desired found!")
			print(date_idx, tot_score)
			continue
		desired_entry = tot_score[date_idx]
		tot_score = {idx: s for idx, s in tot_score.items() if s >= desired_entry}
		for idx, ch, sc in [(i, all_lines[i - 4:i + 20], s) for i, s in tot_score.items()]:
			print(f"----- chunk:{idx} score:{sc}\tis_hit:{idx - date_idx == 0}\t\tname:{name} pdf:{pdf}-----")
			#all_dates = find_dates(all_lines, name)
			#calc_all_score(all_lines, all_dates, dicts[name])

con.commit()
cur.close()
con.close()
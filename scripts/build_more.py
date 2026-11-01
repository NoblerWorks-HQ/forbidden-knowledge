"""Translations, lifespans, genealogies, people (Theographic), sentiment and Matthew's fulfilment quotes.

Called from build_data.py with the KJV books/text/index already built. Every builder
checks its output against known values and exits loudly if a source changed shape.
"""
import json
import re
import sys

SB = "https://raw.githubusercontent.com/scrollmapper/bible_databases/master/formats/json/"
SOURCES = {
    "ylt.json": SB + "YLT.json",
    "darby.json": SB + "Darby.json",
    "webster.json": SB + "Webster.json",
    "web/engwebp_vpl.zip": "https://ebible.org/Scriptures/engwebp_vpl.zip",
    "theo/people.json": "https://raw.githubusercontent.com/robertrouse/theographic-bible-metadata/master/json/people.json",
    "vader.txt": "https://raw.githubusercontent.com/cjhutto/vaderSentiment/master/vaderSentiment/vader_lexicon.txt",
}
# ebible.org's WEB book codes, canonical order
WEB_CODES = ("GEN EXO LEV NUM DEU JOS JDG RUT 1SA 2SA 1KI 2KI 1CH 2CH EZR NEH EST JOB PSA PRO ECC SOL ISA JER LAM "
             "EZE DAN HOS JOE AMO OBA JON MIC NAH HAB ZEP HAG ZEC MAL MAT MAR LUK JOH ACT ROM 1CO 2CO GAL EPH PHI "
             "COL 1TH 2TH 1TI 2TI TIT PHM HEB JAM 1PE 2PE 1JO 2JO 3JO JUD REV").split()


def build_translations(fetch, books, index, clean):
    """{key: [text per KJV verse index]}; a verse a translation lacks is ''."""
    import io
    import zipfile
    n = len(index)
    out = {}
    for key in ("asv", "ylt", "darby", "webster"):
        arr = [""] * n
        for (osis, _, _), book in zip(books, json.loads(fetch(f"{key}.json"))["books"]):
            for ch in book["chapters"]:
                for v in ch["verses"]:
                    i = index.get(f"{osis}.{ch['chapter']}.{v['verse']}")
                    if i is not None:
                        arr[i] = clean(v["text"])
        out[key] = arr
    web = [""] * n
    code_to_osis = {c: books[k][0] for k, c in enumerate(WEB_CODES)}
    vpl = zipfile.ZipFile(io.BytesIO(fetch("web/engwebp_vpl.zip"))).read("engwebp_vpl.txt").decode("utf-8-sig")
    for line in vpl.splitlines():
        m = re.match(r"(\w+) (\d+):(\d+) ?(.*)", line)
        if m and m.group(1) in code_to_osis:
            i = index.get(f"{code_to_osis[m.group(1)]}.{m.group(2)}.{m.group(3)}")
            if i is not None:
                web[i] = m.group(4).strip()
    out["web"] = web
    for key, arr in out.items():
        filled = sum(1 for t in arr if t)
        if filled < n - 200:
            sys.exit(f"translation {key}: only {filled} of {n} verses aligned to the KJV")
    return out


UNITS = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split())}
TENS = {"twenty": 20, "thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90, "threescore": 60, "fourscore": 80, "score": 20}
NUMWORD = set(UNITS) | set(TENS) | {"hundred", "thousand", "an", "a", "and"}


def words_to_int(phrase):
    total, cur = 0, 0
    for w in phrase.lower().split():
        if w in UNITS:
            cur += UNITS[w]
        elif w in TENS:
            cur += TENS[w]
        elif w == "hundred":
            cur = (cur or 1) * 100
        elif w == "thousand":
            # "a thousand thousand" is a million
            total, cur = (total * 1000, 0) if total and not cur else (total + (cur or 1) * 1000, 0)
    return total + cur


def year_numbers(verse):
    """Every number phrase directly followed by 'years' in a verse, in order."""
    toks = re.findall(r"[a-z]+", verse.lower())
    out = []
    for k, t in enumerate(toks):
        if t == "years" and k and toks[k - 1] in NUMWORD and toks[k - 1] not in ("a", "an", "and"):
            j = k - 1
            while j > 0 and toks[j - 1] in NUMWORD:
                j -= 1
            out.append(words_to_int(" ".join(toks[j:k])))
    return out


# name, [(ref, which number phrase)], known value - asserted against the parse
LIFESPANS = [
    ("Adam", [("Gen.5.5", -1)], 930), ("Seth", [("Gen.5.8", -1)], 912), ("Enos", [("Gen.5.11", -1)], 905),
    ("Cainan", [("Gen.5.14", -1)], 910), ("Mahalaleel", [("Gen.5.17", -1)], 895), ("Jared", [("Gen.5.20", -1)], 962),
    ("Enoch", [("Gen.5.23", -1)], 365), ("Methuselah", [("Gen.5.27", -1)], 969), ("Lamech", [("Gen.5.31", -1)], 777),
    ("Noah", [("Gen.9.29", -1)], 950), ("Shem", [("Gen.11.10", 0), ("Gen.11.11", -1)], 600),
    ("Arphaxad", [("Gen.11.12", 0), ("Gen.11.13", -1)], 438), ("Salah", [("Gen.11.14", 0), ("Gen.11.15", -1)], 433),
    ("Eber", [("Gen.11.16", 0), ("Gen.11.17", -1)], 464), ("Peleg", [("Gen.11.18", 0), ("Gen.11.19", -1)], 239),
    ("Reu", [("Gen.11.20", 0), ("Gen.11.21", -1)], 239), ("Serug", [("Gen.11.22", 0), ("Gen.11.23", -1)], 230),
    ("Nahor", [("Gen.11.24", 0), ("Gen.11.25", -1)], 148), ("Terah", [("Gen.11.32", -1)], 205),
    ("Sarah", [("Gen.23.1", -1)], 127), ("Abraham", [("Gen.25.7", -1)], 175), ("Isaac", [("Gen.35.28", -1)], 180),
    ("Jacob", [("Gen.47.28", -1)], 147), ("Joseph", [("Gen.50.26", -1)], 110), ("Aaron", [("Num.33.39", -1)], 123),
    ("Moses", [("Deut.34.7", -1)], 120), ("Joshua", [("Josh.24.29", -1)], 110),
]


def build_lifespans(text, index):
    out = []
    for name, parts, known in LIFESPANS:
        total = 0
        for ref, which in parts:
            nums = year_numbers(text[index[ref]])
            if not nums:
                sys.exit(f"lifespan {name}: no 'N years' phrase in {ref}")
            total += nums[which]
        if total != known:
            sys.exit(f"lifespan {name}: parsed {total} from the text, expected {known}")
        out.append([name, total, index[parts[-1][0]]])
    return out


def build_genealogies(text, index):
    """Matthew 1 (Abraham to Jesus) and Luke 3 (Adam to Jesus) as name lists in the text's order."""
    matt = " ".join(text[index[f"Matt.1.{v}"]] for v in range(2, 17))
    pairs = re.findall(r"([A-Z]\w+)(?: the king)? begat ([A-Z]\w+)", matt)
    chain = [pairs[0][0]]
    for a, b in pairs:
        if a != chain[-1]:
            sys.exit(f"Matthew 1: chain broken at {a} begat {b} (expected {chain[-1]})")
        chain.append(b)
    chain.append("Jesus")
    luke = " ".join(text[index[f"Luke.3.{v}"]] for v in range(23, 39))
    sons = re.findall(r"son of (\w+)", luke)
    lchain = ["Jesus"] + sons
    if chain[0] != "Abraham" or lchain[-1] != "God" or "Adam" not in lchain:
        sys.exit("genealogies: unexpected endpoints")
    return {"matthew": chain, "luke": list(reversed(lchain[:-1]))}


def clean_title(name, t):
    """Theographic's disambiguation labels are free text: keep a short descriptor, drop the rest."""
    while True:
        m = re.fullmatch(re.escape(name) + r"\s*\((.*)\)", t.strip())
        if not m:
            break
        t = m.group(1)
    t = t.strip()
    return "" if not t or t == name or len(t) > 40 or "describes" in t else t


def build_people(fetch):
    """[name, title, gender, verseCount, father, mother, partners, children, birthYear, deathYear, alsoCalled]
    with relations as indexes into this list. Theographic Bible Metadata, CC BY-SA 4.0."""
    raw = json.loads(fetch("theo/people.json"))
    ids = {p["id"]: k for k, p in enumerate(raw)}
    one = lambda v: ids.get(v[0], -1) if v else -1
    many = lambda v: [ids[x] for x in (v or []) if x in ids]
    out = []
    for p in raw:
        f = p["fields"]
        title = clean_title(f["name"], f.get("Disambiguation (temp)") or "")
        out.append([f["name"], title, (f.get("gender") or "")[:1], f.get("verseCount", 0),
                    one(f.get("father")), one(f.get("mother")), many(f.get("partners")), many(f.get("children")),
                    f.get("birthYear", ""), f.get("deathYear", ""), f.get("alsoCalled", "")])
    if len(out) < 2500 or not any(o[0] == "David" and o[7] for o in out):
        sys.exit("people: Theographic format changed")
    return out


def build_sentiment(fetch, books, text):
    """Mean VADER valence per word, per chapter. Archaic KJV words outside the lexicon simply score 0."""
    lex = {}
    for line in fetch("vader.txt").decode().splitlines():
        parts = line.split("\t")
        if len(parts) >= 2 and re.fullmatch(r"[a-z]+", parts[0]):
            lex[parts[0]] = float(parts[1])
    out, i = [], 0
    for _, _, counts in books:
        chs = []
        for c in counts:
            s = w = 0
            for _ in range(c):
                toks = re.findall(r"[a-z]+", text[i].lower())
                w += len(toks)
                s += sum(lex.get(t, 0) for t in toks)
                i += 1
            chs.append(round(s / max(w, 1) * 100, 2))
        out.append(chs)
    return out


NO_SOURCE = {"Matt.2.23"}  # no Old Testament verse says this; the top cross-reference would mislead
# Notes on the debated fulfilment quotes; keys are Matthew references
FULFIL_NOTES = {
    "Matt.1.22": "Isaiah's Hebrew word is almah, “young woman”. The Greek Septuagint, which Matthew quotes, has parthenos, “virgin”.",
    "Matt.2.15": "In Hosea the “son” called out of Egypt is the nation of Israel; Matthew reads it as a pattern repeated in Jesus.",
    "Matt.2.23": "No Old Testament verse says “He shall be called a Nazarene”. Proposed sources include Isaiah 11:1 (Hebrew netzer, “branch”) and the Nazirite vow.",
    "Matt.27.9": "Matthew credits Jeremiah, but the thirty pieces of silver and the potter come from Zechariah 11:12–13.",
}


def build_fulfilment(text, index, rows):
    """Matthew's fulfilment formula verses, each with its highest-voted Old Testament cross-reference."""
    start = index["Matt.1.1"]
    end = index["Mark.1.1"]
    nt_start = index["Matt.1.1"]
    best = {}
    for e in range(0, len(rows), 4):
        f, t, _, v = rows[e:e + 4]
        if start <= f < end and t < nt_start and v > best.get(f, (0, -1))[1]:
            best[f] = (t, v)
    ref_of = {i: r for r, i in index.items()}
    out = []
    for i in range(start, end):
        if re.search(r"might be fulfilled|then was fulfilled|might be accomplished", text[i], re.I):
            cands = [best[j] for j in (i, i + 1) if j in best]
            ot = max(cands, key=lambda x: x[1])[0] if cands else -1
            if ref_of[i] in NO_SOURCE:
                ot = -1
            out.append([i, ot, FULFIL_NOTES.get(ref_of[i], "")])
    if len(out) < 10:
        sys.exit(f"fulfilment: only {len(out)} formula verses found in Matthew")
    return out


def number_phrases(verse):
    """Every number phrase in a verse as an int ("threescore and ten" -> 70)."""
    toks = re.findall(r"[a-z]+", verse.lower())
    out, k = [], 0
    while k < len(toks):
        if toks[k] in NUMWORD and toks[k] not in ("a", "an", "and"):
            j = k
            while j < len(toks) and toks[j] in NUMWORD:
                j += 1
            while toks[j - 1] in ("a", "an", "and"):
                j -= 1
            out.append(words_to_int(" ".join(toks[k:j])))
            k = j
        else:
            k += 1
    return out


# Samuel/Kings vs Chronicles: (what, earlier ref, its number, Chronicles ref, its number), each checked in the text
PARALLELS = [
    ("David's captured horsemen", "2Sam.8.4", 700, "1Chr.18.4", 7000),
    ("Syrian chariot crews killed", "2Sam.10.18", 700, "1Chr.19.18", 7000),
    ("Fighting men of Judah in David's census", "2Sam.24.9", 500000, "1Chr.21.5", 470000),
    ("Fighting men of Israel in David's census", "2Sam.24.9", 800000, "1Chr.21.5", 1100000),
    ("Years of famine offered as punishment", "2Sam.24.13", 7, "1Chr.21.12", 3),
    ("Shekels David paid for the threshing floor", "2Sam.24.24", 50, "1Chr.21.25", 600),
    ("Solomon's horse stalls", "1Kgs.4.26", 40000, "2Chr.9.25", 4000),
    ("Overseers of Solomon's workers", "1Kgs.5.16", 3300, "2Chr.2.2", 3600),
    ("Height of the bronze pillars, in cubits", "1Kgs.7.15", 18, "2Chr.3.15", 35),
    ("Baths the bronze sea held", "1Kgs.7.26", 2000, "2Chr.4.5", 3000),
    ("Chief officers over the work", "1Kgs.9.23", 550, "2Chr.8.10", 250),
    ("Talents of gold from Ophir", "1Kgs.9.28", 420, "2Chr.8.18", 450),
    ("Ahaziah's age when he became king", "2Kgs.8.26", 22, "2Chr.22.2", 42),
    ("Jehoiachin's age when he became king", "2Kgs.24.8", 18, "2Chr.36.9", 8),
]


def build_parallels(text, index):
    out = []
    for what, a, na, b, nb in PARALLELS:
        for ref, n in ((a, na), (b, nb)):
            if n not in number_phrases(text[index[ref]]):
                sys.exit(f"parallels: {n} not found in {ref} ({what})")
        out.append([what, index[a], na, index[b], nb])
    return out

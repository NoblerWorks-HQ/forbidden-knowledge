"""Popes (Wikidata), 1 Enoch (Charles 1917 via Wikisource), Gospels of Thomas and Mary (Mattison, public domain).

Called from build_data.py; each builder fails loudly if its source changed shape.
"""
import html
import json
import re
import sys
import urllib.parse

SPARQL = "https://query.wikidata.org/sparql?format=json&query="
POPE_QUERY = """SELECT ?p ?pLabel ?start ?end ?ord ?kind WHERE {
  VALUES ?kind { wd:Q19546 wd:Q172748 }
  ?p p:P39 ?st. ?st ps:P39 ?kind.
  OPTIONAL { ?st pq:P580 ?start } OPTIONAL { ?st pq:P582 ?end } OPTIONAL { ?st pq:P1545 ?ord }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en". } }"""
WIKISOURCE = "https://en.wikisource.org/w/api.php?action=parse&prop=wikitext&format=json&page="

SOURCES = {
    "hist/popes.json": SPARQL + urllib.parse.quote(POPE_QUERY),
    "hist/thomas.htm": "https://www.gospels.net/thomas",
    "hist/mary.htm": "https://www.gospels.net/mary",
}
for _c in range(1, 109):
    SOURCES[f"hist/enoch/{_c:03d}.json"] = WIKISOURCE + urllib.parse.quote(f"The Book of Enoch (Charles)/Chapter {_c:02d}")

ANTIPOPE = "Q172748"


def build_popes(fetch):
    """[ordinal, name, start, end, antipope] sorted by start; fails if the papal line has gaps."""
    seen, out = set(), []
    for b in json.loads(fetch("hist/popes.json"))["results"]["bindings"]:
        anti = b["kind"]["value"].endswith(ANTIPOPE)
        start = b.get("start", {}).get("value", "")[:10]
        if not start or (not anti and "ord" not in b):
            continue
        key = (b["p"]["value"], start, anti)
        if key in seen:
            continue
        seen.add(key)
        name = re.sub(r"^(Pope|Saint|Antipope) ", "", b["pLabel"]["value"])
        out.append([0 if anti else int(b["ord"]["value"]), name, start, b.get("end", {}).get("value", "")[:10], int(anti)])
    ords = sorted(p[0] for p in out if not p[4])
    if ords != list(range(1, len(ords) + 1)) or len(ords) < 266:
        missing = sorted(set(range(1, max(ords) + 1)) - set(ords))
        sys.exit(f"pope ordinals are not a clean 1..N line (missing {missing[:10]}, {len(ords)} rows)")
    return sorted(out, key=lambda p: p[2])


def clean_wiki(t):
    t = re.sub(r"\{\{header.*?\n\}\}", "", t, flags=re.S)
    t = re.sub(r"<ref[^>]*>.*?</ref>|<ref[^>]*/>", "", t, flags=re.S)
    t = re.sub(r"\{\{[^{}]*\}\}", "", t)
    t = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", t)
    t = re.sub(r"^=+.*?=+\s*$|^CHAPTER [IVXLC]+\.?\s*$", "", t, flags=re.M)
    t = re.sub(r"<[^>]+>|'{2,}", "", t)
    return re.sub(r"\s+", " ", t.replace("⌈", "").replace("⌉", "")).strip()


def build_enoch(fetch):
    """[label, text] verses per chapter. Charles relocates verses and splits some (14a, 14b),
    so a marker counts when it moves forward by at most 4 or adds a letter to the same number."""
    chapters = []
    for c in range(1, 109):
        text = clean_wiki(json.loads(fetch(f"hist/enoch/{c:03d}.json"))["parse"]["wikitext"]["*"])
        text = text.replace("||", " ").replace("†", "")
        verses, prev, prev_sfx, cur, label = [], 0, "", None, None
        for m in re.finditer(r"(?:^|\s)(\d{1,3})([a-d]?)\. ", text):
            n, sfx = int(m.group(1)), m.group(2)
            if not (prev < n <= prev + 4 or (n == prev and sfx and sfx != prev_sfx)):
                continue  # a number inside the text, not a verse marker
            if cur is not None:
                verses.append([label, re.sub(r"\s+", " ", text[cur:m.start()]).strip()])
            cur, label, prev, prev_sfx = m.end(), f"{n}{sfx}", n, sfx
        if cur is None:
            sys.exit(f"Enoch chapter {c}: no verse numbers found")
        verses.append([label, re.sub(r"\s+", " ", text[cur:]).strip()])
        chapters.append(verses)
    longest = max(len(v[1]) for ch in chapters for v in ch)
    if longest > 2000:  # a few relocated half-verses (89:48b) legitimately run long
        sys.exit(f"Enoch: a {longest}-character verse means verse markers were missed")
    return chapters


def page_lines(fetch, name):
    s = fetch(name).decode()
    s = html.unescape(re.sub(r"<(script|style)[^>]*>.*?</\1>", "", s, flags=re.S))
    s = re.sub(r"<br\s*/?>|</p>|</h\d>|</div>|</li>", "\n", s)
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in re.sub(r"<[^>]+>", "", s).split("\n")]
    lines = [ln for ln in lines if ln]
    start = next(i for i, ln in enumerate(lines) if "committed to the public domain" in ln)
    end = next(i for i in range(start, len(lines) - 1) if lines[i] == "The Gospel" and lines[i + 1].startswith("According to"))
    body = lines[start + 1:end]
    first = next(i for i, ln in enumerate(body) if ln in ("Prologue",) or ln.startswith("Pages 1 "))
    return body[first:]


def build_thomas(fetch):
    """[number, title, text]; 0 is the prologue."""
    sayings, cur = [], None
    for ln in page_lines(fetch, "hist/thomas.htm"):
        m = re.match(r"Saying (\d+): (.*)", ln)
        if ln == "Prologue" or m:
            cur = [int(m.group(1)) if m else 0, m.group(2) if m else "Prologue", ""]
            sayings.append(cur)
        elif cur:
            cur[2] = (cur[2] + "\n" + ln).strip()
    if [s[0] for s in sayings] != list(range(0, 115)):
        sys.exit("Thomas: expected a prologue and sayings 1-114")
    return sayings


def build_mary(fetch):
    """[heading, text] sections; manuscript page numbers removed, lost pages kept as notes."""
    sections, cur = [], None
    for ln in page_lines(fetch, "hist/mary.htm"):
        if ln.startswith("Pages ") and "missing" in ln:
            sections.append(["", ln])
            cur = None
        elif len(ln) < 40 and not re.search(r"[.;:,!?\"'”’]$", ln) and not ln[0].isdigit() and not ln.startswith(("The first", "The second", "The third", "The fourth", "The fifth", "The sixth", "The seventh", "[")):
            cur = [ln, ""]
            sections.append(cur)
        elif cur is not None:
            cur[1] = (cur[1] + "\n" + re.sub(r"(^|\s)(?:[7-9]|1\d)\s(?=\S)", r"\1", ln)).strip()
    if sum(1 for s in sections if s[0]) < 4:
        sys.exit(f"Mary: only {len(sections)} sections parsed")
    return sections

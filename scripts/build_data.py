#!/usr/bin/env python3
"""Download the source texts and write the compact data files site/index.html loads.

Sources (cached in ~/.cache/versegraph):
  - OpenBible.info cross-references (CC BY): https://www.openbible.info/labs/cross-references/
  - KJV text (public domain) via scrollmapper/bible_databases
  - Moby Dick (public domain) via Project Gutenberg, header/footer stripped

  - Bible geocoding (CC BY 4.0): https://github.com/openbibleinfo/Bible-Geocoding-Data
  - ASV text (public domain) for divine-name counts - it renders YHWH as "Jehovah"
  - Natural Earth coastlines, lakes and rivers (public domain)
  - popes, 1 Enoch, Thomas and Mary: see build_extra.py
  - translations, people (Theographic, CC BY-SA 4.0), sentiment lexicon: see build_more.py

Writes site/data/{bible.json,xrefs.json,moby.txt,places.json,land.json,theories.json,popes.json,extra.json,more.json,people.json,tr-*.json}. Fails loudly if any
cross-reference does not resolve to a KJV verse beyond a small, known tolerance.
"""
import io, json, pathlib, re, sys, time, urllib.request, zipfile

import build_extra
import build_more
import build_world
import build_library

ROOT = pathlib.Path(__file__).resolve().parent.parent
CACHE = pathlib.Path.home() / ".cache" / "versegraph"
OUT = ROOT / "site" / "data"

SOURCES = {
    "xrefs.zip": "https://a.openbible.info/data/cross-references.zip",
    "kjv.json": "https://raw.githubusercontent.com/scrollmapper/bible_databases/master/formats/json/KJV.json",
    "moby.txt": "https://www.gutenberg.org/cache/epub/2701/pg2701.txt",
    "asv.json": "https://raw.githubusercontent.com/scrollmapper/bible_databases/master/formats/json/ASV.json",
    "geo/ancient.jsonl": "https://raw.githubusercontent.com/openbibleinfo/Bible-Geocoding-Data/main/data/ancient.jsonl",
}
NE = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/"
SOURCES.update(build_extra.SOURCES)
SOURCES.update(build_more.SOURCES)
SOURCES.update(build_world.SOURCES)
SOURCES.update(build_library.SOURCES)
for _layer in ("ne_50m_land", "ne_10m_lakes", "ne_50m_rivers_lake_centerlines"):
    SOURCES[f"geo/{_layer}.geojson"] = f"{NE}{_layer}.geojson"

BBOX = (8.0, 18.0, 56.0, 45.0)  # lon0, lat0, lon1, lat1 - Rome to Persia, Nubia to the Black Sea
LAKES = {"Sea of Galilee", "Dead Sea", "Lake Van", "Lake Urmia", "Lake Tuz", "Lake Sevan", "Great Bitter Lake", "Lake Hammar"}
RIVERS = {"Nile", "Jordan", "Euphrates", "Firat", "Al Furat", "Tigris", "Dicle", "Shatt al Arab", "Damietta Branch", "Rosetta Branch"}
STOP = set("the and of to that in he shall unto for i his a they be is him not them it with all thou thy was which my me but ye their have thee from as are when this out were by upon there then so said on what one into an".split())

# OSIS code, display name - in canonical order, matching the KJV file.
BOOKS = [
    ("Gen", "Genesis"), ("Exod", "Exodus"), ("Lev", "Leviticus"), ("Num", "Numbers"), ("Deut", "Deuteronomy"),
    ("Josh", "Joshua"), ("Judg", "Judges"), ("Ruth", "Ruth"), ("1Sam", "1 Samuel"), ("2Sam", "2 Samuel"),
    ("1Kgs", "1 Kings"), ("2Kgs", "2 Kings"), ("1Chr", "1 Chronicles"), ("2Chr", "2 Chronicles"), ("Ezra", "Ezra"),
    ("Neh", "Nehemiah"), ("Esth", "Esther"), ("Job", "Job"), ("Ps", "Psalms"), ("Prov", "Proverbs"),
    ("Eccl", "Ecclesiastes"), ("Song", "Song of Solomon"), ("Isa", "Isaiah"), ("Jer", "Jeremiah"), ("Lam", "Lamentations"),
    ("Ezek", "Ezekiel"), ("Dan", "Daniel"), ("Hos", "Hosea"), ("Joel", "Joel"), ("Amos", "Amos"),
    ("Obad", "Obadiah"), ("Jonah", "Jonah"), ("Mic", "Micah"), ("Nah", "Nahum"), ("Hab", "Habakkuk"),
    ("Zeph", "Zephaniah"), ("Hag", "Haggai"), ("Zech", "Zechariah"), ("Mal", "Malachi"), ("Matt", "Matthew"),
    ("Mark", "Mark"), ("Luke", "Luke"), ("John", "John"), ("Acts", "Acts"), ("Rom", "Romans"),
    ("1Cor", "1 Corinthians"), ("2Cor", "2 Corinthians"), ("Gal", "Galatians"), ("Eph", "Ephesians"), ("Phil", "Philippians"),
    ("Col", "Colossians"), ("1Thess", "1 Thessalonians"), ("2Thess", "2 Thessalonians"), ("1Tim", "1 Timothy"), ("2Tim", "2 Timothy"),
    ("Titus", "Titus"), ("Phlm", "Philemon"), ("Heb", "Hebrews"), ("Jas", "James"), ("1Pet", "1 Peter"),
    ("2Pet", "2 Peter"), ("1John", "1 John"), ("2John", "2 John"), ("3John", "3 John"), ("Jude", "Jude"),
    ("Rev", "Revelation"),
]
MAX_UNRESOLVED = 50  # versification differences between OpenBible and this KJV file


def fetch(name):
    path = CACHE / name
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        print(f"downloading {SOURCES[name]}")
        req = urllib.request.Request(SOURCES[name], headers={"User-Agent": "forbidden-knowledge-build/0.1 (+https://github.com/NoblerWorks-HQ/forbidden-knowledge)"})
        path.write_bytes(urllib.request.urlopen(req, timeout=60).read())
        time.sleep(0.3)  # polite to Wikisource and Wikidata
    return path.read_bytes()


def clean(text):
    text = re.sub(r"^[א-ת] [A-Z]+\.\s*", "", text)  # Psalm 119 acrostic headings
    return text.replace("[", "").replace("]", "").replace("’", "'").strip()


def main():
    kjv = json.loads(fetch("kjv.json"))
    if len(kjv["books"]) != len(BOOKS):
        sys.exit(f"KJV has {len(kjv['books'])} books, expected {len(BOOKS)}")
    books, text, index = [], [], {}
    for (osis, name), book in zip(BOOKS, kjv["books"]):
        counts = []
        for ch in book["chapters"]:
            counts.append(len(ch["verses"]))
            for v in ch["verses"]:
                index[f"{osis}.{ch['chapter']}.{v['verse']}"] = len(text)
                text.append(clean(v["text"]))
        books.append([osis, name, counts])

    raw = zipfile.ZipFile(io.BytesIO(fetch("xrefs.zip"))).read("cross_references.txt").decode()
    rows, unresolved, dropped_votes = [], 0, 0
    for line in raw.splitlines()[1:]:
        src, dst, votes = line.split("\t")
        votes = int(votes)
        if votes < 1:
            dropped_votes += 1
            continue
        a, _, b = dst.partition("-")
        try:
            f, t0 = index[src], index[a]
            t1 = index[b] if b else t0
        except KeyError:
            unresolved += 1
            continue
        rows += [f, t0, t1 - t0, votes]
    if unresolved > MAX_UNRESOLVED:
        sys.exit(f"{unresolved} cross-references did not resolve to KJV verses (limit {MAX_UNRESOLVED})")

    moby = fetch("moby.txt").decode("utf-8-sig")
    start = moby.index("CHAPTER 1. Loomings.", moby.index("CHAPTER 1. Loomings.") + 1)
    end = moby.index("*** END OF THE PROJECT GUTENBERG")

    places = build_places(index)
    land = build_land()
    theories = build_theories(books, text, rows)
    popes = build_extra.build_pope_bios(fetch, SOURCES, build_extra.build_popes(fetch))
    extra = {k: getattr(build_extra, f"build_{k}")(fetch) for k in ("enoch", "thomas", "mary")}
    translations = build_more.build_translations(fetch, books, index, clean)
    people = build_more.build_people(fetch)
    more = {
        "lifespans": build_more.build_lifespans(text, index),
        "genealogies": build_more.build_genealogies(text, index),
        "sentiment": build_more.build_sentiment(fetch, books, text),
        "fulfilment": build_more.build_fulfilment(text, index, rows),
        "parallels": build_more.build_parallels(text, index),
    }

    bom = build_world.build_bom(fetch)
    world = {"quran": build_world.build_quran(fetch), "bom": bom, "bomKjv": build_world.build_bom_kjv(bom, text),
             "quotes": build_world.build_quotes(fetch)}

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "world.json").write_text(json.dumps(world, separators=(",", ":")))
    library = build_library.build_library(fetch, text, index, world, extra, SOURCES)
    (OUT / "library.json").write_text(json.dumps(library, separators=(",", ":"), ensure_ascii=False))
    (OUT / "places.json").write_text(json.dumps(places, separators=(",", ":")))
    (OUT / "land.json").write_text(json.dumps(land, separators=(",", ":")))
    (OUT / "theories.json").write_text(json.dumps(theories, separators=(",", ":")))
    (OUT / "popes.json").write_text(json.dumps(popes, separators=(",", ":")))
    (OUT / "extra.json").write_text(json.dumps(extra, separators=(",", ":")))
    (OUT / "more.json").write_text(json.dumps(more, separators=(",", ":")))
    (OUT / "people.json").write_text(json.dumps(people, separators=(",", ":")))
    for key, arr in translations.items():
        (OUT / f"tr-{key}.json").write_text(json.dumps(arr, separators=(",", ":")))
    (OUT / "bible.json").write_text(json.dumps({"books": books, "text": text}, separators=(",", ":")))
    (OUT / "xrefs.json").write_text(json.dumps(rows, separators=(",", ":")))
    (OUT / "moby.txt").write_text(moby[start:end].strip() + "\n")
    print(f"{len(text)} verses, {len(rows)//4} cross-references kept, "
          f"{dropped_votes} with votes < 1 dropped, {unresolved} unresolved")
    print(f"{len(places)} mapped places, {sum(len(x) for x in land.values())} map shapes, "
          f"synoptic: {theories['synoptic']['counts']}")
    print(f"{sum(1 for p in popes if not p[4])} popes, {sum(1 for p in popes if p[4])} antipopes; "
          f"Enoch {len(extra['enoch'])} chapters, {sum(map(len, extra['enoch']))} verses; "
          f"Thomas {len(extra['thomas']) - 1} sayings; Mary {len(extra['mary'])} sections")
    print(f"translations {sorted(translations)}; {len(people)} people; {len(more['lifespans'])} lifespans; "
          f"genealogies Matt {len(more['genealogies']['matthew'])} / Luke {len(more['genealogies']['luke'])}; "
          f"{len(more['fulfilment'])} fulfilment verses")
    print(f"Quran {sum(len(s[3]) for s in world['quran'])} verses; Book of Mormon {sum(len(c) for _, chs in bom for c in chs)} verses, "
          f"{len(world['bomKjv'])} mostly KJV wording")
    print(f"library: {', '.join(f'{k} {len(v)}' for k, v in library['passages'].items())}; "
          f"{len(library['parallels'])} parallels, {len(library['shared'])} Apocrypha/KJV links")


def tag_free(html):
    return re.sub(r"<[^>]+>", "", html).strip()


def build_places(index):
    """Ancient places with every proposed modern identification, best first."""
    out, missing = [], 0
    for line in fetch("geo/ancient.jsonl").decode().splitlines():
        rec = json.loads(line)
        cands = []
        for ident in rec.get("identifications", []):
            res = (ident.get("resolutions") or [{}])[0]
            if not res.get("lonlat"):
                continue
            lon, lat = (round(float(x), 4) for x in res["lonlat"].split(","))
            cands.append([tag_free(ident["description"]), lon, lat, ident["score"].get("vote_total", 0)])
        verses = sorted({index[v["osis"]] for v in rec.get("verses", []) if v["osis"] in index})
        if not cands or not verses:
            missing += 1
            continue
        cands.sort(key=lambda c: -c[3])
        out.append({"n": rec["friendly_id"], "t": (rec.get("types") or ["place"])[0], "c": cands, "v": verses})
    if len(out) < 1000:
        sys.exit(f"only {len(out)} places resolved ({missing} skipped) - geocoding format changed?")
    return out


def build_land():
    """Coastlines, natural lakes and major rivers inside BBOX, rounded to ~1 km."""
    lon0, lat0, lon1, lat1 = BBOX

    def ring(coords):
        pts, last = [], None
        for x, y in coords:
            pt = [round(x, 2), round(y, 2)]
            if pt != last:
                pts.append(pt)
                last = pt
        return pts if any(lon0 - 5 < x < lon1 + 5 and lat0 - 5 < y < lat1 + 5 for x, y in pts) else None

    def shapes(layer, keep=lambda props: True, holes=True, everywhere=False):
        out = []
        for ft in json.loads(fetch(f"geo/{layer}.geojson"))["features"]:
            if not keep(ft["properties"]):
                continue
            g = ft["geometry"]
            parts = {"Polygon": [g["coordinates"]], "MultiPolygon": g["coordinates"],
                     "LineString": [[g["coordinates"]]], "MultiLineString": [[c] for c in g["coordinates"]]}[g["type"]]
            for part in parts:
                for r in part[: None if holes else 1]:
                    r2 = ring(r) if not everywhere else [[round(x, 2), round(y, 2)] for x, y in r]
                    if r2 and len(r2) > 1:
                        out.append(r2)
        return out

    return {
        "land": shapes("ne_50m_land", holes=False, everywhere=True),
        "lakes": shapes("ne_10m_lakes", lambda p: p.get("name") in LAKES, holes=False),
        "rivers": shapes("ne_50m_rivers_lake_centerlines", lambda p: p.get("name") in RIVERS),
    }


def words(t):
    return {w for w in re.findall(r"[a-z]+", t.lower()) if len(w) > 2 and w not in STOP}


def build_theories(books, text, rows):
    # Divine names in Genesis, ASV: "Jehovah" = YHWH, "God" = Elohim
    asv = json.loads(fetch("asv.json"))["books"][0]["chapters"]
    jehovah = [sum(len(re.findall(r"\bJehovah\b", v["text"])) for v in c["verses"]) for c in asv]
    god = [sum(len(re.findall(r"\bGod\b", v["text"])) for v in c["verses"]) for c in asv]

    # Synoptic parallels: a cross-reference between two synoptic gospels whose wording overlaps
    book_of = []
    for b, (_, _, counts) in enumerate(books):
        book_of += [b] * sum(counts)
    names = {"Matt": 39, "Mark": 40, "Luke": 41}
    if [books[i][0] for i in names.values()] != list(names):
        sys.exit("synoptic book indexes moved")
    syn = set(names.values())
    par = {}
    for e in range(0, len(rows), 4):
        a, b = rows[e], rows[e + 1]
        if book_of[a] in syn and book_of[b] in syn and book_of[a] != book_of[b]:
            wa, wb = words(text[a]), words(text[b])
            if wa and wb and len(wa & wb) / len(wa | wb) >= 0.10:  # tuned: ~81% of Mark, ~234 Matt-Luke-only verses
                par.setdefault(a, set()).add(book_of[b])
                par.setdefault(b, set()).add(book_of[a])
    counts = {}
    for name, b in names.items():
        others = [o for o in names.values() if o != b]
        label = {o: books[o][0] for o in others}
        c = {"total": 0, "both": 0, label[others[0]]: 0, label[others[1]]: 0, "none": 0}
        for v in range(len(text)):
            if book_of[v] != b:
                continue
            c["total"] += 1
            p = par.get(v, set())
            c["both" if all(o in p for o in others) else next((label[o] for o in others if o in p), "none")] += 1
        counts[name] = c
    return {"genesis": {"jehovah": jehovah, "god": god}, "synoptic": {"counts": counts}}


if __name__ == "__main__":
    main()

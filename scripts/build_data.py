#!/usr/bin/env python3
"""Download the source texts and write the compact data files site/index.html loads.

Sources (cached in ~/.cache/versegraph):
  - OpenBible.info cross-references (CC BY): https://www.openbible.info/labs/cross-references/
  - KJV text (public domain) via scrollmapper/bible_databases
  - Moby Dick (public domain) via Project Gutenberg, header/footer stripped

Writes site/data/{bible.json,xrefs.json,moby.txt}. Fails loudly if any
cross-reference does not resolve to a KJV verse beyond a small, known tolerance.
"""
import io, json, pathlib, re, sys, urllib.request, zipfile

ROOT = pathlib.Path(__file__).resolve().parent.parent
CACHE = pathlib.Path.home() / ".cache" / "versegraph"
OUT = ROOT / "site" / "data"

SOURCES = {
    "xrefs.zip": "https://a.openbible.info/data/cross-references.zip",
    "kjv.json": "https://raw.githubusercontent.com/scrollmapper/bible_databases/master/formats/json/KJV.json",
    "moby.txt": "https://www.gutenberg.org/cache/epub/2701/pg2701.txt",
}

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
        CACHE.mkdir(parents=True, exist_ok=True)
        print(f"downloading {SOURCES[name]}")
        req = urllib.request.Request(SOURCES[name], headers={"User-Agent": "versegraph-build"})
        path.write_bytes(urllib.request.urlopen(req, timeout=60).read())
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

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "bible.json").write_text(json.dumps({"books": books, "text": text}, separators=(",", ":")))
    (OUT / "xrefs.json").write_text(json.dumps(rows, separators=(",", ":")))
    (OUT / "moby.txt").write_text(moby[start:end].strip() + "\n")
    print(f"{len(text)} verses, {len(rows)//4} cross-references kept, "
          f"{dropped_votes} with votes < 1 dropped, {unresolved} unresolved")


if __name__ == "__main__":
    main()

"""Scriptures beyond the Bible: the Quran (Pickthall 1930, via Tanzil), the Book of Mormon (1830, Project
Gutenberg), and short checked quotations from the Analects (Legge) and the Dhammapada (Müller).

Called from build_data.py; each builder fails loudly if its source changed shape.
"""
import re
import sys

SOURCES = {
    "world/quran-pickthall.txt": "https://tanzil.net/trans/?transID=en.pickthall&type=txt-2",
    "world/quran-data.xml": "https://tanzil.net/res/text/metadata/quran-data.xml",
    "world/bom.txt": "https://www.gutenberg.org/cache/epub/17/pg17.txt",
    "world/analects.txt": "https://www.gutenberg.org/cache/epub/3330/pg3330.txt",
    "world/dhammapada.txt": "https://www.gutenberg.org/cache/epub/2017/pg2017.txt",
}


def build_quran(fetch):
    """{suras: [[transliterated name, English name, Meccan/Medinan, [verses]]]} in the standard order."""
    meta = re.findall(r'<sura index="(\d+)" ayas="(\d+)"[^>]*tname="([^"]+)" ename="([^"]+)" type="(\w+)"', fetch("world/quran-data.xml").decode())
    suras = [[t, e, ty, []] for _, _, t, e, ty in meta]
    for line in fetch("world/quran-pickthall.txt").decode("utf-8-sig").splitlines():
        m = re.match(r"(\d+)\|(\d+)\|(.*)", line)
        if m:
            s, a = int(m.group(1)), int(m.group(2))
            if a != len(suras[s - 1][3]) + 1:
                sys.exit(f"Quran: sura {s} verse {a} out of order")
            suras[s - 1][3].append(m.group(3).strip())
    if len(suras) != 114 or sum(len(s[3]) for s in suras) != 6236 or any(len(s[3]) != int(m[1]) for s, m in zip(suras, meta)):
        sys.exit("Quran: expected 114 suras and 6,236 verses matching the Tanzil metadata")
    return suras


# One-chapter books announced by a title line instead of "Book Chapter 1"
SINGLE = {"THE BOOK OF ENOS": "Enos", "THE BOOK OF JAROM": "Jarom", "THE BOOK OF OMNI": "Omni", "THE WORDS OF MORMON": "Words of Mormon"}


def build_bom(fetch):
    """[[book, [[verse text per chapter]]]]; chapter headers read '1 Nephi Chapter 1', verses '1:1 text'."""
    t = fetch("world/bom.txt").decode("utf-8-sig").replace("\r", "")
    t = t[t.index("1 Nephi Chapter 1"):t.index("*** END OF THE PROJECT GUTENBERG")]
    books, cur = [], None
    for para in re.split(r"\n\s*\n", t):
        para = " ".join(para.split())
        if para.startswith("4 Nephi 1:"):  # this one-chapter book prefixes every verse instead of a header
            if books[-1][0] != "4 Nephi":
                books.append(["4 Nephi", [[]]])
                cur = books[-1][1][-1]
            para = para[len("4 Nephi "):]
        if para in SINGLE:
            books.append([SINGLE[para], [[]]])
            cur = books[-1][1][-1]
            continue
        h = re.fullmatch(r"(.+?) Chapter (\d+)", para)
        if h:
            if not books or books[-1][0] != h.group(1):
                books.append([h.group(1), []])
            books[-1][1].append([])
            cur = books[-1][1][-1]
            continue
        if cur is None:
            continue
        # A marker starts a verse only when it is the next verse of this chapter; a few verses share a paragraph
        ch, pos = len(books[-1][1]), 0
        for m in re.finditer(r"(?:^|(?<=\s))(\d+):(\d+) ", para):
            if int(m.group(1)) == ch and int(m.group(2)) == len(cur) + 1:
                if cur and pos:
                    cur[-1] += " " + para[pos:m.start()].strip()
                elif pos == 0 and m.start() > 0 and cur:
                    cur[-1] += " " + para[:m.start()].strip()
                cur.append("")
                pos = m.end()
        if pos:
            cur[-1] = (cur[-1] + " " + para[pos:]).strip()
        elif cur:
            cur[-1] += " " + para  # a verse that runs over a blank line
    n = sum(len(c) for _, chs in books for c in chs)
    if len(books) != 15 or not 6500 < n < 6700:
        sys.exit(f"Book of Mormon: {len(books)} books, {n} verses (expected 15 books, ~6,604 verses)")
    return books


def build_bom_kjv(bom, text):
    """Book of Mormon verses whose wording is mostly a single KJV verse: [bom flat index, kjv index, share]."""
    tok = lambda s: [w for w in re.findall(r"[a-z]+", s.lower())]
    inv = {}
    for i, v in enumerate(text):
        for w in set(tok(v)):
            inv.setdefault(w, []).append(i)
    common = {w for w, l in inv.items() if len(l) > 3000}
    out, k = [], 0
    for _, chs in bom:
        for ch in chs:
            for v in ch:
                ws = set(tok(v)) - common
                if len(ws) >= 6:
                    score = {}
                    for w in ws:
                        for i in inv.get(w, ()):
                            score[i] = score.get(i, 0) + 1
                    if score:
                        best = max(score, key=score.get)
                        share = score[best] / len(ws)
                        if share >= 0.8 and len(set(tok(text[best])) - common) <= len(ws) * 1.4:
                            out.append([k, best, round(share, 2)])
                k += 1
    if len(out) < 300:
        sys.exit(f"Book of Mormon/KJV overlap: only {len(out)} verses matched; the matcher or a source changed")
    return out


# Quotations shown in the app, each checked against the downloaded text
QUOTES = {
    "analects": ("world/analects.txt", "What you do not want done to yourself, do not do to others."),
    "dhammapada": ("world/dhammapada.txt", "For hatred does not cease by hatred at any time: hatred ceases by love"),
}


def build_quotes(fetch):
    out = {}
    for k, (name, q) in QUOTES.items():
        body = " ".join(fetch(name).decode("utf-8-sig").split())
        if q not in body:
            sys.exit(f"quote {k} not found in {name}")
        out[k] = q
    return out

"""The Library: texts beyond the Bible, and computed connections between all of them.

New texts (all public domain): the Apocrypha (KJV 1611 via scrollmapper), the Epic of Gilgamesh
(R. Campbell Thompson 1928, archive.org OCR), the Code of Hammurabi (C. H. W. Johns 1903),
the Tao Te Ching (Legge 1891), the Dhammapada (Müller 1881) and the Bhagavad Gita (Arnold 1885).
Texts already built elsewhere (KJV, Quran, Book of Mormon, 1 Enoch, Thomas) are referenced, not copied.

Connections are passages that share unusually many distinctive words (IDF-weighted overlap). They show shared
vocabulary and stories, not proof of borrowing, and translators' styles matter: Pickthall, the Book of Mormon
and Charles all write in KJV-like English. Landmark parallels are curated and asserted against the text.
"""
import math
import re
import sys

SB = "https://raw.githubusercontent.com/scrollmapper/bible_databases/master/formats/json/"
SOURCES = {
    "lib/kjva.json": SB + "KJVA.json",
    "lib/gilgamesh.txt": "https://archive.org/download/thompson-1928-gilgamesh/Thompson_1928_Gilgamesh_djvu.txt",
    "lib/hammurabi.txt": "https://www.gutenberg.org/cache/epub/17150/pg17150.txt",
    "lib/tao.txt": "https://www.gutenberg.org/cache/epub/216/pg216.txt",
    "lib/gita.txt": "https://www.gutenberg.org/cache/epub/2388/pg2388.txt",
    "world/dhammapada.txt": "https://www.gutenberg.org/cache/epub/2017/pg2017.txt",
}

# id, name, tradition, written (label), sort year, translation
TEXTS = [
    ("gilgamesh", "Epic of Gilgamesh", "Mesopotamia", "c. 1800–1200 BC", -1800, "R. Campbell Thompson, 1928"),
    ("hammurabi", "Code of Hammurabi", "Mesopotamia", "c. 1754 BC", -1754, "C. H. W. Johns, 1903"),
    ("kjv", "The Bible", "Judaism and Christianity", "c. 1000 BC – AD 100", -1000, "King James Version, 1611/1769"),
    ("tao", "Tao Te Ching", "Taoism", "c. 4th century BC", -350, "James Legge, 1891"),
    ("enoch", "1 Enoch", "Second Temple Judaism", "c. 300–1 BC", -300, "R. H. Charles, 1917"),
    ("dhamma", "Dhammapada", "Buddhism", "c. 3rd century BC", -250, "F. Max Müller, 1881"),
    ("apoc", "The Apocrypha", "Judaism and Christianity", "c. 300 BC – AD 100", -200, "King James Version, 1611"),
    ("gita", "Bhagavad Gita", "Hinduism", "c. 2nd century BC – 2nd century AD", -100, "Edwin Arnold, 1885"),
    ("thomas", "Gospel of Thomas", "Early Christianity", "1st–2nd century AD", 120, "Mark M. Mattison"),
    ("quran", "The Quran", "Islam", "AD 610–632", 620, "Marmaduke Pickthall, 1930"),
    ("bom", "Book of Mormon", "Latter-day Saints", "1830", 1830, "Joseph Smith, 1830"),
]
APOC = ["I Esdras", "II Esdras", "Tobit", "Judith", "Additions to Esther", "Wisdom", "Sirach", "Baruch", "Prayer of Azariah",
        "Susanna", "Bel and the Dragon", "Prayer of Manasses", "I Maccabees", "II Maccabees"]
ROMAN = "FIRST SECOND THIRD FOURTH FIFTH SIXTH SEVENTH EIGHTH NINTH TENTH ELEVENTH TWELFTH".split()


def gutenberg_body(raw):
    t = raw.decode("utf-8-sig").replace("\r", "")
    a = t.find("*** START OF")
    b = t.find("*** END OF")
    return t[t.index("\n", a) + 1 if a >= 0 else 0: b if b >= 0 else None]


def build_apocrypha(fetch):
    import json
    books = {b["name"]: b for b in json.loads(fetch("lib/kjva.json"))["books"]}
    out = []
    for name in APOC:
        for ch in books[name]["chapters"]:
            for v in ch["verses"]:
                out.append([f"{name.replace('II ', '2 ').replace('I ', '1 ')} {ch['chapter']}:{v['verse']}", " ".join(v["text"].split())])
    if len(out) < 5000:
        sys.exit(f"Apocrypha: only {len(out)} verses")
    return out


def build_gilgamesh(fetch):
    """Four-line passages per tablet; OCR line numbers, running heads, notes and column headings removed."""
    t = fetch("lib/gilgamesh.txt").decode("utf-8", "replace")
    heads = [(m.start(), ROMAN.index(m.group(1)) + 1) for m in re.finditer(r"^THE (" + "|".join(ROMAN) + r") TABLET\.? *$", t, re.M)]
    if len(heads) < 10:
        sys.exit(f"Gilgamesh: only {len(heads)} tablet headings found")
    out = []
    for k, (pos, n) in enumerate(heads):
        body = t[pos: heads[k + 1][0] if k + 1 < len(heads) else len(t)]
        lines = []
        for ln in body.split("\n")[1:]:
            ln = ln.strip()
            if (not ln or re.fullmatch(r"[\d.,\s]+", ln) or "EPIC OF GILGAMISH" in ln.upper() or re.match(r"(?i)no[t]?[eg]s?\b|notgs|column\b", ln)
                    or re.fullmatch(r"\(.*\)\.?", ln) or ln.isupper() or len(ln) < 12):
                continue
            lines.append(re.sub(r"^[\d\]r]+(?=[A-Z“\"(])", "", ln))
        for i in range(0, len(lines), 4):
            out.append([f"Tablet {n}.{i // 4 + 1}", " ".join(lines[i:i + 4])])
    if not any("dove" in p[1] for p in out):
        sys.exit("Gilgamesh: the flood passage with the dove is missing")
    return out


def build_hammurabi(fetch):
    t = gutenberg_body(fetch("lib/hammurabi.txt"))
    out = []
    for m in re.finditer(r"^section (\d+)\.\s+(.*?)(?=\n\s*\n)", t, re.M | re.S):
        out.append([f"Law {m.group(1)}", " ".join(m.group(2).split())])
    nums = [int(p[0][4:]) for p in out]
    if len(out) < 240 or 196 not in nums:
        sys.exit(f"Hammurabi: {len(out)} laws parsed")
    return out


def build_tao(fetch):
    t = gutenberg_body(fetch("lib/tao.txt"))
    # A chapter starts after two blank lines; short chapters have no "1." paragraph number
    starts = [(m.start(1), int(m.group(1))) for m in re.finditer(r"(?:^|\n\n\n)(?:Ch\. )?(\d+)\.(?=\s)", t)]
    starts = [s for k, s in enumerate(starts) if s[1] == (starts[k - 1][1] + 1 if k else 1)]
    out = []
    for k, (pos, n) in enumerate(starts):
        body = t[pos: starts[k + 1][0] if k + 1 < len(starts) else t.find("\n\n\n\n", pos)]
        out.append([f"Ch. {n}", " ".join(re.sub(r"^\d+\.\s+(?:1\.\s+)?", "", body).split())])
    if len(out) != 81:
        sys.exit(f"Tao Te Ching: {len(out)} chapters, expected 81")
    return out


def build_dhamma(fetch):
    t = gutenberg_body(fetch("world/dhammapada.txt"))
    out, want = [], 1
    # Müller sometimes joins verses: "58, 59. As on a heap of rubbish..."
    for m in re.finditer(r"^(\d+)((?:, \d+)*)\. (.*?)(?=\n\s*\n)", t, re.M | re.S):
        if int(m.group(1)) == want:
            last = int(m.group(2).split(", ")[-1]) if m.group(2) else want
            out.append([f"v. {want}" + (f"–{last}" if last != want else ""), " ".join(m.group(3).split())])
            want = last + 1
    if want != 424:
        sys.exit(f"Dhammapada: parsed up to verse {want - 1}, expected 423")
    return out


def build_gita(fetch):
    t = gutenberg_body(fetch("lib/gita.txt"))
    parts = re.split(r"^ *CHAPTER ([IVXL]+)\s*$", t, flags=re.M)
    out = []
    for k in range(1, len(parts), 2):
        stanzas = [" ".join(s.split()) for s in re.split(r"\n\s*\n", parts[k + 1]) if len(" ".join(s.split())) > 60]
        for j, s in enumerate(stanzas):
            if "HERE ENDETH" in s.upper():
                continue
            out.append([f"Ch. {k // 2 + 1}.{j + 1}", s])
    if len({p[0].rsplit(".", 1)[0] for p in out}) != 18:
        sys.exit("Bhagavad Gita: expected 18 chapters")
    return out


STOP = set("""the and of to that in he shall unto for his a they be is him not them it with all thou thy was which my me but ye
their have thee from as are when this out were by upon there then so said on what one into an i we you your our us she her
who whom will would may might can could hath had has did do does doth done also even if or nor no yea lo behold now these
those such any every each more most other than very own same which while upon say saith says said came come cometh went go
let made make like man men things thing day days time great good god lord""".split())


def stem(w):
    for suf in ("eth", "est", "ing", "ed", "es", "s"):
        if w.endswith(suf) and len(w) - len(suf) >= 4:
            return w[: -len(suf)]
    return w


def toks(s):
    return {stem(w) for w in re.findall(r"[a-z]+", s.lower()) if len(w) > 2 and w not in STOP}


def connect(corpus, threshold=0.34, per_pair=150):
    """corpus: {text id: [passage text]}. Returns [ta, ia, tb, ib, score] for passages in different texts."""
    ids = list(corpus)
    docs = [(t, i, toks(p)) for t in ids for i, p in enumerate(corpus[t])]
    N = len(docs)
    df = {}
    for _, _, ws in docs:
        for w in ws:
            df[w] = df.get(w, 0) + 1
    idf = {w: math.log(N / c) for w, c in df.items() if c <= N * 0.004}
    inv = {}
    weight = []
    for d, (t, i, ws) in enumerate(docs):
        ws = [w for w in ws if w in idf]
        weight.append(sum(idf[w] for w in ws))
        for w in ws:
            inv.setdefault(w, []).append(d)
    best = {}
    for d, (t, i, ws) in enumerate(docs):
        if t == "kjv" or weight[d] == 0:
            continue  # the KJV is only ever a target; its internal links are the OpenBible cross-references
        acc, shared = {}, {}
        for w in ws:
            if w not in idf:
                continue
            for e in inv[w]:
                if docs[e][0] != t:
                    acc[e] = acc.get(e, 0) + idf[w]
                    shared[e] = shared.get(e, 0) + 1
        top = {}
        for e, s in acc.items():
            if shared[e] < 3 or not weight[e]:
                continue
            score = s / math.sqrt(weight[d] * weight[e])
            if score >= threshold and score > top.get(docs[e][0], (0,))[0]:
                top[docs[e][0]] = (score, e)
        for tb, (score, e) in top.items():
            a, b = (d, e) if d < e else (e, d)
            key = (docs[a][0], docs[b][0])
            best.setdefault(key, {})[(docs[a][1], docs[b][1])] = round(score, 3)
    edges = []
    for (ta, tb), pairs in best.items():
        for (ia, ib), sc in sorted(pairs.items(), key=lambda x: -x[1])[:per_pair]:
            edges.append([ta, ia, tb, ib, sc])
    return edges


def find(passages, needle, label=None):
    for k, (lab, txt) in enumerate(passages):
        if (label is None or lab == label) and needle in txt:
            return k
    sys.exit(f"landmark: {needle!r} not found" + (f" in {label}" if label else ""))


# Curated parallels: (text, anchor), (text, anchor), kind, note. Anchors: KJV "Gen.8.7"; Quran (sura, aya);
# Book of Mormon (book, chapter, verse); 1 Enoch (chapter, "verse"); Thomas saying number; other texts a label
# ("Law 196") or a phrase in the passage. Every anchor is resolved and checked at build time.
PARALLELS = [
    (("gilgamesh", "fashion a vessel"), ("kjv", "Gen.6.14"), "story", "A god warns one man to build a boat before the flood."),
    (("gilgamesh", "Pitch did the children"), ("kjv", "Gen.6.14"), "story", "The boat is sealed with pitch, in both."),
    (("gilgamesh", "seed of all living"), ("kjv", "Gen.6.19"), "story", "The hero takes aboard his family and the seed of every living thing."),
    (("gilgamesh", "put forth a dove"), ("kjv", "Gen.8.8"), "story", "When the waters fall, birds are sent out: a dove that returns, then others."),
    (("gilgamesh", "the raven went"), ("kjv", "Gen.8.7"), "story", "A raven that does not return."),
    (("gilgamesh", "did assemble like flies"), ("kjv", "Gen.8.21"), "story", "After the flood a sacrifice, and the gods smell its sweet savour."),
    (("gilgamesh", "Finger’d some clay"), ("kjv", "Gen.2.7"), "idea", "A god shapes a man from clay."),
    (("gilgamesh", "a serpent who snuff"), ("kjv", "Gen.3.22"), "idea", "Immortality lost to a serpent: it steals Gilgamesh's plant of life, as Adam loses the tree of life."),
    (("gilgamesh", "mouth of the rivers"), ("quran", (18, 60)), "story", "A hero journeys to where the rivers meet to find a wise immortal. Scholars link Sura 18's Moses and Khidr to this story and to the Alexander romance."),
    (("hammurabi", "Law 196"), ("kjv", "Exod.21.24"), "law", "Eye for an eye, about 500 years before Exodus was written."),
    (("hammurabi", "Law 209"), ("kjv", "Exod.21.22"), "law", "A man strikes a pregnant woman and she miscarries: both laws set a payment."),
    (("hammurabi", "Law 251"), ("kjv", "Exod.21.29"), "law", "The owner of an ox known to gore who did not restrain it."),
    (("hammurabi", "Law 250"), ("kjv", "Exod.21.28"), "law", "An ox that gores a man to death."),
    (("hammurabi", "Law 14"), ("kjv", "Exod.21.16"), "law", "Kidnapping is punished by death."),
    (("hammurabi", "Law 117"), ("kjv", "Exod.21.2"), "law", "Debt slavery with a fixed release: three years in Hammurabi, six in Exodus."),
    (("enoch", (1, "9")), ("kjv", "Jude.1.14"), "quote", "Jude quotes Enoch by name."),
    (("enoch", (6, "2")), ("kjv", "Gen.6.2"), "story", "The sons of God take human wives."),
    (("enoch", (10, "4")), ("kjv", "Jude.1.6"), "story", "Fallen angels bound in darkness until the judgement."),
    (("enoch", (46, "1")), ("kjv", "Dan.7.9"), "idea", "The Head of Days and the Son of Man, after Daniel's vision."),
    (("enoch", (62, "5")), ("kjv", "Matt.25.31"), "idea", "The Son of Man on the throne of his glory."),
    (("apoc", "Tobit 4:15"), ("kjv", "Matt.7.12"), "saying", "The Golden Rule, in its negative form, two centuries before Jesus."),
    (("apoc", "Wisdom 13:5"), ("kjv", "Rom.1.20"), "idea", "God known through his creation; Paul seems to know Wisdom."),
    (("apoc", "Wisdom 2:18"), ("kjv", "Matt.27.43"), "idea", "If he is God's son, let God deliver him: the mockery at the cross echoes Wisdom."),
    (("apoc", "Sirach 28:2"), ("kjv", "Matt.6.14"), "saying", "Forgive, and you will be forgiven."),
    (("apoc", "1 Maccabees 4:59"), ("kjv", "John.10.22"), "story", "The feast of dedication, Hanukkah, which Jesus attends in John."),
    (("apoc", "2 Maccabees 7:9"), ("kjv", "Heb.11.35"), "story", "Martyrs who refused release to obtain a better resurrection."),
    (("tao", "Ch. 63"), ("kjv", "Matt.5.44"), "idea", "Recompense injury with kindness; love your enemies."),
    (("tao", "Ch. 81"), ("kjv", "Acts.20.35"), "idea", "The more the sage gives to others, the more he has."),
    (("dhamma", "v. 5"), ("kjv", "Matt.5.44"), "idea", "Hatred ceases by love."),
    (("dhamma", "v. 252"), ("kjv", "Matt.7.3"), "saying", "Others' faults are easy to see, your own hard: the mote and the beam."),
    (("dhamma", "v. 103"), ("kjv", "Prov.16.32"), "saying", "Whoever conquers himself is greater than one who conquers a city or an army."),
    (("gita", "Manifold the renewals"), ("kjv", "John.1.14"), "idea", "God taking flesh: Krishna is born again whenever righteousness declines; the Word became flesh."),
    (("thomas", 54), ("kjv", "Luke.6.20"), "saying", "Blessed are the poor."),
    (("thomas", 26), ("kjv", "Matt.7.3"), "saying", "The speck and the beam."),
    (("thomas", 9), ("kjv", "Mark.4.3"), "saying", "The parable of the sower."),
    (("thomas", 20), ("kjv", "Mark.4.31"), "saying", "The mustard seed."),
    (("thomas", 47), ("kjv", "Luke.5.37"), "saying", "New wine in old wineskins."),
    (("thomas", 64), ("kjv", "Luke.14.16"), "saying", "The great dinner whose guests make excuses."),
    (("thomas", 100), ("kjv", "Mark.12.17"), "saying", "Give Caesar what is Caesar's."),
    (("thomas", 107), ("kjv", "Luke.15.4"), "saying", "The lost sheep."),
    (("quran", (21, 105)), ("kjv", "Ps.37.29"), "quote", "The Quran says this is written in the Psalms (Zabur): the righteous will inherit the earth."),
    (("quran", (7, 40)), ("kjv", "Matt.19.24"), "saying", "A camel through the eye of a needle."),
    (("quran", (19, 19)), ("kjv", "Luke.1.31"), "story", "An angel announces to Mary that she will bear a son."),
    (("quran", (12, 4)), ("kjv", "Gen.37.9"), "story", "Joseph dreams that the sun, the moon and eleven stars bow to him."),
    (("quran", (20, 20)), ("kjv", "Exod.4.3"), "story", "Moses casts down his staff and it becomes a serpent."),
    (("quran", (28, 7)), ("kjv", "Exod.2.3"), "story", "Moses' mother sets the baby on the river."),
    (("quran", (37, 103)), ("kjv", "Gen.22.10"), "story", "Abraham lays his son down for sacrifice. The Quran does not name the son; most Muslim scholars say Ishmael."),
    (("quran", (11, 44)), ("kjv", "Gen.8.4"), "story", "The ark comes to rest: on al-Judi in the Quran, on the mountains of Ararat in Genesis."),
    (("quran", (27, 23)), ("kjv", "1Kgs.10.1"), "story", "Solomon and the Queen of Sheba."),
    (("bom", ("3 Nephi", 12, 3)), ("kjv", "Matt.5.3"), "quote", "The Sermon on the Mount, given again to the Nephites, in KJV wording."),
    (("bom", ("2 Nephi", 12, 2)), ("kjv", "Isa.2.2"), "quote", "Isaiah chapters copied in KJV wording."),
    (("bom", ("Mosiah", 14, 5)), ("kjv", "Isa.53.5"), "quote", "Isaiah 53, the suffering servant."),
    (("bom", ("3 Nephi", 24, 10)), ("kjv", "Mal.3.10"), "quote", "Jesus gives the Nephites Malachi's words."),
]
KINDS = {"quote": "Quotes", "story": "Same story", "law": "Same law", "saying": "Same saying", "idea": "Similar idea"}


def build_library(fetch, kjv_text, kjv_index, world, extra):
    texts = {k: getattr(sys.modules[__name__], "build_" + b)(fetch) for k, b in
             [("apoc", "apocrypha"), ("gilgamesh", "gilgamesh"), ("hammurabi", "hammurabi"), ("tao", "tao"), ("dhamma", "dhamma"), ("gita", "gita")]}
    qstart, n = [], 0
    for s in world["quran"]:
        qstart.append(n)
        n += len(s[3])
    bom_at, n = {}, 0
    for name, chs in world["bom"]:
        for c, ch in enumerate(chs):
            for v in range(len(ch)):
                bom_at[(name, c + 1, v + 1)] = n
                n += 1
    enoch_at, n = {}, 0
    for c, ch in enumerate(extra["enoch"]):
        for label, _ in ch:
            enoch_at[(c + 1, label)] = n
            n += 1

    def resolve(t, a):
        try:
            if t == "kjv":
                return kjv_index[a]
            if t == "quran":
                if a[1] > len(world["quran"][a[0] - 1][3]):
                    raise KeyError(a)
                return qstart[a[0] - 1] + a[1] - 1
            if t == "bom":
                return bom_at[a]
            if t == "enoch":
                return enoch_at[a]
            if t == "thomas":
                if extra["thomas"][a][0] != a:
                    raise KeyError(a)
                return a
        except (KeyError, IndexError):
            sys.exit(f"parallel anchor {t} {a!r} not found")
        exact = [k for k, (lab, _) in enumerate(texts[t]) if lab == a]
        return exact[0] if exact else find(texts[t], a)

    parallels = [[ta, resolve(ta, a), tb, resolve(tb, b), kind, note] for (ta, a), (tb, b), kind, note in PARALLELS]
    # Shared wording only where texts really share it: the KJV Apocrypha quoting or retelling the KJV
    shared = connect({"apoc": [p[1] for p in texts["apoc"]], "kjv": kjv_text}, threshold=0.5, per_pair=400)
    if len(shared) < 80:
        sys.exit(f"library: only {len(shared)} Apocrypha/KJV shared-wording links")
    return {"texts": [dict(zip(("id", "name", "trad", "written", "y", "tr"), t)) for t in TEXTS],
            "passages": texts, "parallels": parallels, "shared": shared, "kinds": KINDS}

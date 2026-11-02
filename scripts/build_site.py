#!/usr/bin/env python3
"""Build the public site in dist/ from site/ and site/data/ (run build_data.py first).

- dist/index.html: the app, wrapped in a full HTML document (the artifact host adds this wrapper itself)
- dist/read/<book>/<chapter>.html: one indexable page per chapter (1,189), each verse with its
  strongest cross-references linking to other chapter pages
- dist/read/index.html, sitemap.xml, robots.txt, CNAME, .nojekyll, 404.html
"""
import html
import json
import pathlib
import re
import shutil
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE, DIST = ROOT / "site", ROOT / "dist"
HOST = "forbidden.noblerworks.com"
BASE = f"https://{HOST}"
DESC = ("Lost civilizations, secret societies, banned books and Bible codes, every claim checked against the sources: "
        "an 11,000-year scroll-through timeline, Giza theories, giants, alchemy, Gnostics, Templars, Rosicrucians, Freemasons and the Illuminati, the Book of Enoch, "
        "the Quran and the Book of Mormon beside the KJV, and an honest test of Bible codes.")
XREFS_PER_VERSE = 3
MIN_VOTES = 5

PAGE_CSS = """
:root { --bg:#fafafa; --surface:#fff; --ink:#0a0a0a; --muted:#6b6b6b; --rule:#e5e5e5; --rubric:#c2410c; --gold:#f97316; }
@media (prefers-color-scheme: dark) { :root { --bg:#0a0a0a; --surface:#171717; --ink:#fafafa; --muted:#a3a3a3; --rule:#2a2a2a; --rubric:#fb923c; --gold:#f97316; color-scheme: dark; } }
* { box-sizing: border-box; }
body { margin: 0; background: var(--bg); color: var(--ink); font: 17px/1.65 Literata, Georgia, serif; }
main { max-width: 760px; margin: 0 auto; padding: 28px max(16px, env(safe-area-inset-left)) 64px; }
a { color: inherit; text-decoration-color: var(--rule); text-underline-offset: 3px; }
a:hover { text-decoration-color: var(--gold); }
header { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; flex-wrap: wrap; border-bottom: 1px solid var(--rule); padding-bottom: 10px; font: 500 14px Geist, system-ui, sans-serif; }
header .mark { font: 26px "IM Fell English SC", Georgia, serif; text-decoration: none; }
header .mark span { color: var(--rubric); }
h1 { font: 400 34px "IM Fell English SC", Georgia, serif; margin: 22px 0 4px; }
.sub { color: var(--muted); font: 14px system-ui, sans-serif; margin: 0 0 18px; }
.v { padding: 8px 0; border-bottom: 1px solid var(--rule); }
.v sup { color: var(--rubric); font: 600 12px ui-monospace, monospace; margin-right: 6px; }
.x { font: 13px system-ui, sans-serif; color: var(--muted); margin-top: 2px; }
.x a { margin-right: 10px; white-space: nowrap; }
nav.pn { display: flex; justify-content: space-between; gap: 12px; margin-top: 22px; font: 500 15px system-ui, sans-serif; }
.books { columns: 3 220px; font: 15px system-ui, sans-serif; }
.books div { break-inside: avoid; margin-bottom: 14px; }
.books b { display: block; }
.books a { display: inline-block; min-width: 2.2em; }
footer { margin-top: 40px; padding-top: 12px; border-top: 1px solid var(--rule); color: var(--muted); font: 12px system-ui, sans-serif; }
"""
# A red eye with a gold iris on the night background, inline so there is no favicon request to 404
ICON = ('<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns=%27http://www.w3.org/2000/svg%27 viewBox=%270 0 32 32%27%3E'
        '%3Crect width=%2732%27 height=%2732%27 rx=%276%27 fill=%27%230d1220%27/%3E%3Cpath d=%27M4 16q12-12 24 0q-12 12-24 0z%27 '
        'fill=%27none%27 stroke=%27%23e0664c%27 stroke-width=%272.4%27/%3E%3Ccircle cx=%2716%27 cy=%2716%27 r=%274.2%27 fill=%27%23d9b45a%27/%3E%3C/svg%3E">')
FONTS = '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IM+Fell+English+SC&family=Literata:opsz@7..72&display=swap">'
FOOTER = ('<footer>Text: King James Version (public domain). Cross-references from '
          '<a href="https://www.openbible.info/labs/cross-references/">OpenBible.info</a> (CC BY). '
          'Built by <a href="https://noblerworks.com">Nobler Works</a>. '
          '<a href="https://github.com/NoblerWorks-HQ/forbidden-knowledge">Source</a>.</footer>')


def slug(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def doc(title, desc, canonical, body, extra_head=""):
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
            f"<title>{html.escape(title)}</title><meta name=\"description\" content=\"{html.escape(desc)}\">"
            f'<link rel="canonical" href="{canonical}"><meta property="og:title" content="{html.escape(title)}">'
            f'<meta property="og:description" content="{html.escape(desc)}"><meta property="og:url" content="{canonical}">'
            f'<meta property="og:type" content="website">{ICON}{extra_head}</head><body>{body}</body></html>')


def main():
    data = SITE / "data"
    if not (data / "bible.json").exists():
        sys.exit("site/data is missing - run scripts/build_data.py first")
    bible = json.loads((data / "bible.json").read_text())
    xr = json.loads((data / "xrefs.json").read_text())
    books, text = bible["books"], bible["text"]

    if DIST.exists():
        shutil.rmtree(DIST)
    shutil.copytree(data, DIST / "data")
    shutil.copytree(SITE / "img", DIST / "img")  # public-domain images, credited in the page

    # The app: the artifact page is a fragment (title, style, markup, script); give it a real document.
    app = (SITE / "index.html").read_text()
    app = re.sub(r'<meta charset="utf-8">\s*|<title>.*?</title>\s*|<meta name="claude:viewport-fit-sides"[^>]*>\s*', "", app, count=3)
    # The artifact host's wrapper zeroes the body margin; do the same here.
    (DIST / "index.html").write_text(doc("Forbidden Knowledge", DESC, BASE + "/", app, "<style>body{margin:0}</style>"))

    # verse index -> (book, chapter, verse)
    loc = []
    for b, (_, _, counts) in enumerate(books):
        for c, n in enumerate(counts):
            loc += [(b, c + 1, v + 1) for v in range(n)]
    out = {}
    for e in range(0, len(xr), 4):
        f, t, span, votes = xr[e:e + 4]
        if votes >= MIN_VOTES:
            out.setdefault(f, []).append((votes, t, span))

    def href(i):
        b, c, v = loc[i]
        return f"/read/{slug(books[b][1])}/{c}.html#v{v}"

    def label(i, span=0):
        b, c, v = loc[i]
        if not span:
            return f"{books[b][1]} {c}:{v}"
        _, c2, v2 = loc[i + span]
        return f"{books[b][1]} {c}:{v}–{v2 if c2 == c else f'{c2}:{v2}'}"

    urls = [BASE + "/", BASE + "/read/"]
    chapters = [(b, c) for b, (_, _, counts) in enumerate(books) for c in range(1, len(counts) + 1)]
    i = 0
    for k, (b, c) in enumerate(chapters):
        name = books[b][1]
        n = books[b][2][c - 1]
        rows = []
        for v in range(1, n + 1):
            refs = sorted(out.get(i, []), reverse=True)[:XREFS_PER_VERSE]
            xs = "".join(f'<a href="{href(t)}">{html.escape(label(t, s))}</a>' for _, t, s in refs)
            rows.append(f'<div class="v" id="v{v}"><sup>{v}</sup>{html.escape(text[i])}'
                        + (f'<div class="x">See also: {xs}</div>' if xs else "") + "</div>")
            i += 1
        prev_l = f'<a href="/read/{slug(books[chapters[k-1][0]][1])}/{chapters[k-1][1]}.html">← {books[chapters[k-1][0]][1]} {chapters[k-1][1]}</a>' if k else "<span></span>"
        next_l = f'<a href="/read/{slug(books[chapters[k+1][0]][1])}/{chapters[k+1][1]}.html">{books[chapters[k+1][0]][1]} {chapters[k+1][1]} →</a>' if k + 1 < len(chapters) else "<span></span>"
        title = f"{name} {c} (KJV) with cross-references"
        first = text[i - n]
        desc = f"{name} {c} in the King James Version, with the strongest cross-references for each verse. {first[:110]}"
        canonical = f"{BASE}/read/{slug(name)}/{c}.html"
        body = (f'<main><header><a class="mark" href="/">Forbidden <span>Knowledge</span></a><a href="/read/">All books</a></header>'
                f'<h1>{html.escape(name)} {c}</h1><p class="sub">King James Version · {n} verses · '
                f'<a href="/#verse/{books[b][0]}.{c}.1">Explore cross-references interactively</a></p>{"".join(rows)}'
                f'<nav class="pn">{prev_l}{next_l}</nav>{FOOTER}</main>')
        page = DIST / "read" / slug(name) / f"{c}.html"
        page.parent.mkdir(parents=True, exist_ok=True)
        page.write_text(doc(title, desc, canonical, body, FONTS + f"<style>{PAGE_CSS}</style>"))
        urls.append(canonical)

    idx = "".join(f'<div><b>{html.escape(name)}</b>' + "".join(f'<a href="/read/{slug(name)}/{c}.html">{c}</a> ' for c in range(1, len(counts) + 1)) + "</div>"
                  for _, name, counts in books)
    (DIST / "read" / "index.html").write_text(doc(
        "Read the King James Bible with cross-references", "Every chapter of the King James Bible, each verse with its strongest cross-references.",
        BASE + "/read/", f'<main><header><a class="mark" href="/">Forbidden <span>Knowledge</span></a><a href="/">Explore</a></header><h1>Read</h1>'
        f'<p class="sub">All 66 books and 1,189 chapters of the King James Version.</p><div class="books">{idx}</div>{FOOTER}</main>',
        FONTS + f"<style>{PAGE_CSS}</style>"))

    (DIST / "404.html").write_text(doc("Not found · Forbidden Knowledge", "Page not found.", BASE + "/404.html",
                                       f'<main><h1>Not found</h1><p><a href="/">Go to Forbidden Knowledge</a> or <a href="/read/">read by chapter</a>.</p></main>',
                                       f"<style>{PAGE_CSS}</style>"))
    (DIST / "sitemap.xml").write_text('<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
                                      + "".join(f"<url><loc>{u}</loc></url>\n" for u in urls) + "</urlset>\n")
    (DIST / "robots.txt").write_text(f"User-agent: *\nAllow: /\nSitemap: {BASE}/sitemap.xml\n")
    (DIST / "CNAME").write_text(HOST + "\n")
    (DIST / ".nojekyll").write_text("")
    if len(urls) != 1189 + 2:
        sys.exit(f"expected 1,191 sitemap URLs, built {len(urls)}")
    total = sum(p.stat().st_size for p in DIST.rglob("*") if p.is_file())
    print(f"dist/: {len(urls)} URLs in the sitemap, {total / 1e6:.1f} MB")


if __name__ == "__main__":
    main()

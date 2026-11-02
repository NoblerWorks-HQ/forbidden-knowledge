#!/usr/bin/env python3
"""Social preview images (1200x630) in site/og/: one per section in VIEW_INFO, plus home and read.

Each card is the section's public-domain image under the site's wordmark, title and blurb. Needs Pillow
(`~/.cache/motion-studio-venv/bin/python scripts/build_og.py`); fonts are IM Fell English (OFL), fetched once
into ~/.cache/versegraph/fonts. Re-run after adding a section or changing a VIEW_INFO title or blurb; the
output is committed, so build_site.py needs no Pillow.
"""
import json
import pathlib
import re
import sys
import urllib.request

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = pathlib.Path(__file__).resolve().parent.parent
SITE, OUT = ROOT / "site", ROOT / "site" / "og"
FONTS = pathlib.Path.home() / ".cache" / "versegraph" / "fonts"
FONT_URLS = {"sc": "imfellenglishsc/IMFeENsc28P.ttf", "rm": "imfellenglish/IMFeENrm28P.ttf"}
W, H = 1200, 630
NIGHT, GOLD, RED, PAPER, MUTED = (13, 18, 32), (217, 180, 90), (224, 102, 76), (244, 238, 226), (176, 168, 152)
# Sections whose VIEW_INFO has no picture (glyph tiles and the scripture tools)
FALLBACK = {"home": "flammarion", "kabbalah": "sefirot", "religions": "buddha", "arcs": "kjv", "verse": "isaiah", "path": "patmos",
            "ladder": "jerome", "myths": "eve", "theories": "vaticanus", "map": "piri", "people": "abraham",
            "translations": "jerome", "numbers": "voynich", "codes": "voynich"}
EXTRA = {"home": ["Forbidden Knowledge", "Lost civilizations, secret societies, banned books and Bible codes, every claim checked against the sources"],
         "read": ["Read the King James Bible", "Every chapter, each verse with its strongest cross-references"]}


def font(kind, size):
    path = FONTS / pathlib.Path(FONT_URLS[kind]).name
    if not path.exists():
        FONTS.mkdir(parents=True, exist_ok=True)
        path.write_bytes(urllib.request.urlopen("https://github.com/google/fonts/raw/main/ofl/" + FONT_URLS[kind], timeout=60).read())
    return ImageFont.truetype(str(path), size)


def view_info():
    s = (SITE / "index.html").read_text()
    block = s[s.index("const VIEW_INFO = {"):]
    block = block[:block.index("\n};")]
    return {k: json.loads(v) for k, v in re.findall(r'^  (\w+): (\[.*\]),$', block, re.M)}


def wrap(draw, text, f, width, max_lines):
    lines, cur = [], ""
    for w in text.split():
        t = f"{cur} {w}".strip()
        if draw.textlength(t, font=f) <= width:
            cur = t
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        while draw.textlength(lines[-1] + "…", font=f) > width:
            lines[-1] = lines[-1].rsplit(" ", 1)[0]
        lines[-1] = lines[-1].rstrip(",;:") + "…"
    return lines


def card(title, blurb, img):
    src = Image.open(SITE / "img" / f"{img}.jpg").convert("RGB")
    # The picture fills the right half; a solid night panel on the left carries the type
    pw, solid, ramp = 660, 560, 170
    scale = max(pw / src.width, H / src.height)
    pic = src.resize((round(src.width * scale), round(src.height * scale)), Image.LANCZOS)
    pic = pic.crop(((pic.width - pw) // 2, (pic.height - H) // 2, (pic.width - pw) // 2 + pw, (pic.height - H) // 2 + H))
    out = Image.new("RGB", (W, H), NIGHT)
    blur = src.resize((W, round(src.height * W / src.width)) if src.width / src.height < W / H else (round(src.width * H / src.height), H)).crop((0, 0, W, H))
    out.paste(Image.blend(blur.filter(ImageFilter.GaussianBlur(30)).resize((W, H)), Image.new("RGB", (W, H), NIGHT), 0.82))
    out.paste(pic, (W - pw, 0))
    fade = Image.new("L", (W, H), 0)
    fd = ImageDraw.Draw(fade)
    for x in range(W):
        a = 255 if x < solid else round(255 * (1 - (x - solid) / ramp) ** 1.5) if x < solid + ramp else 0
        fd.line([(x, 0), (x, H)], fill=a)
    out.paste(Image.new("RGB", (W, H), NIGHT), (0, 0), fade)
    d = ImageDraw.Draw(out)
    x, maxw = 60, 480
    d.text((x, 58), "Forbidden", font=font("sc", 34), fill=PAPER)
    d.text((x + d.textlength("Forbidden ", font=font("sc", 34)), 58), "Knowledge", font=font("sc", 34), fill=RED)
    d.line([(x, 112), (x + 70, 112)], fill=GOLD, width=3)
    size = 76 if d.textlength(title, font=font("sc", 76)) <= maxw else 60
    tl = wrap(d, title, font("sc", size), maxw, 2)
    y = 150
    for line in tl:
        d.text((x, y), line, font=font("sc", size), fill=PAPER)
        y += round(size * 1.08)
    y += 18
    for line in wrap(d, blurb, font("rm", 32), maxw, 6 - len(tl)):
        d.text((x, y), line, font=font("rm", 32), fill=(222, 214, 198))
        y += 42
    d.text((x, H - 96), "Every claim checked", font=font("rm", 26), fill=GOLD)
    d.text((x, H - 62), "forbidden.noblerworks.com", font=font("rm", 26), fill=MUTED)
    return out


def main():
    info = view_info()
    if len(info) < 25:
        sys.exit(f"VIEW_INFO: parsed only {len(info)} sections")
    OUT.mkdir(exist_ok=True)
    jobs = {k: (v[0], v[1], (v[2] if len(v) > 2 and v[2] else None) or FALLBACK.get(k)) for k, v in info.items()}
    jobs["home"] = (EXTRA["home"][0], EXTRA["home"][1], FALLBACK["home"])
    jobs["read"] = (EXTRA["read"][0], EXTRA["read"][1], "kjv")
    for k, (title, blurb, img) in jobs.items():
        if not img:
            sys.exit(f"og: no picture for section {k!r}; add it to FALLBACK")
        card(title, blurb, img).save(OUT / f"{k}.jpg", quality=84, optimize=True)
    print(f"og: {len(jobs)} images in {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

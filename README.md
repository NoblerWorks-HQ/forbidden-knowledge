# Versegraph

Data exploration over the 341,282 reader-voted cross-references between the
31,102 verses of the King James Bible, plus an honest "Bible code" (ELS) search.

- **Arcs** - every cross-reference as an arc, colored by reach; filter by book and vote count.
- **Verse** - look up a verse and its cross-references, strongest first.
- **Path** - shortest chain of cross-references between two verses (BFS, strongest link wins ties).
- **Ladder** - daily game: climb from one verse to another by cross-references; par is the BFS shortest path.
- **Myths** - misconceptions checked against the text, an "Is that in the Bible?" phrase checker, computed facts, word dispersion.
- **Theories** - YHWH vs Elohim per chapter of Genesis (ASV), synoptic overlap of Matthew, Mark and Luke.
- **Map** - every geocoded place by book, plus every proposed site for disputed places (Sinai, Red Sea, Eden...).
- **Beyond the Canon** - 1 Enoch, Nag Hammadi, Thomas, Mary, Philip, Judas, the Gospel of Jesus' Wife forgery;
  Enoch-Bible parallels; full readers for 1 Enoch, Thomas and Mary with "closest Bible verses" per passage.
- **History** - papal succession by century (Wikidata) with antipopes; Shroud, Eucharistic miracles, Templars, Pope Joan, the arks.
- **Beyond the Bible** - Religions (Pew 2020 shares, names across the Bible/Quran/Book of Mormon, Book of Mormon vs KJV overlap computed at build, Quran reader with closest Bible verses), Philosophy (Pascal's wager calculator, arguments, misquotes), Lost Worlds (Göbekli Tepe, Atlantis, Giza theories, real and fake lost technology, giants, forbidden knowledge), Conspiracies (Illuminati, Protocols, Bible Mandela effect checked against the text, antichrists).
- **Timeline** - scroll-driven story from the pyramids to the Dead Sea Scrolls: a pinned map flies between places, journeys draw in, and the year scrubs with the scroll.
- **Quiz, heatmap, links** - a daily five-question quiz under the Ladder, a book-to-book citation heatmap under Arcs, and shareable verse links (`#verse/John.3.16`).
- **More checks** - Kings vs Chronicles number disagreements (asserted at build), where "hell" comes from (via Young's Literal), Lucifer, 666/616, lost books, failed end dates, Dead Sea Scroll readings.
- **Mysteries** - Egypt in the Bible (mentions by book, pharaohs matched to Egyptian records, Amenemope, the Aten hymn, myths), the Bible in Masonic ritual, the Rosicrucian manifestos, and the Psalm 46 "Shakespeare" count computed live. Tim Hogan's Templar/Egypt claims checked one by one against the text and the record.
- **People** - lifespans parsed from the text, Matthew vs Luke genealogies, family explorer (Theographic).
- **Translations** - KJV, Webster, YLT, Darby, ASV and WEB side by side with differences marked; the 16 verses newer Bibles drop.
- **Numbers** - number-word frequencies, a gematria coincidence machine, Atbash and the alphabet acrostics.
- **Code Breaker** - equidistant letter sequence search run on the KJV, *Moby Dick* and the
  KJV's letters shuffled, each next to the count expected from letter frequencies alone.

One static page (`site/index.html`), no build step, no backend.

## Build the data

```bash
python3 scripts/build_data.py   # downloads sources to ~/.cache/versegraph, writes site/data/
python3 -m http.server -d site  # then open http://localhost:8000
```

## Public site

`scripts/deploy-pages.sh` rebuilds the data, builds `dist/` (the app plus one indexable page per
chapter, sitemap, CNAME) and commits it to the `gh-pages` branch, which GitHub Pages serves at
https://versegraph.noblerworks.com. `--dry-run` builds without pushing.

## Sources and licenses

- Cross-references: [OpenBible.info](https://www.openbible.info/labs/cross-references/), CC BY
  (attribution required - kept in the page footer).
- KJV text: public domain, via [scrollmapper/bible_databases](https://github.com/scrollmapper/bible_databases).
- *Moby Dick*: public domain, Project Gutenberg #2701 (header and license text stripped).
- Place identifications: [OpenBible.info Bible Geocoding Data](https://github.com/openbibleinfo/Bible-Geocoding-Data), CC BY 4.0.
- ASV text (divine-name counts): public domain. Map shapes: Natural Earth, public domain.
- Popes and antipopes: Wikidata, CC0.
- 1 Enoch: R. H. Charles translation (1917), public domain, via Wikisource.
- Gospels of Thomas and Mary: Mark M. Mattison's translations, dedicated to the public domain (gospels.net).
- Translations: ASV, YLT, Darby and Webster via scrollmapper/bible_databases; World English Bible from ebible.org. All public domain.
- People: [Theographic Bible Metadata](https://github.com/robertrouse/theographic-bible-metadata), CC BY-SA 4.0 (so `site/data/people.json` is CC BY-SA too).
- Sentiment: VADER lexicon, MIT.
- Code: MIT.

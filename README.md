# Versegraph

Data exploration over the 341,282 reader-voted cross-references between the
31,102 verses of the King James Bible, plus an honest "Bible code" (ELS) search.

- **Arcs** - every cross-reference as an arc, colored by reach; filter by book and vote count.
- **Verse** - look up a verse and its cross-references, strongest first.
- **Path** - shortest chain of cross-references between two verses (BFS, strongest link wins ties).
- **Code Breaker** - equidistant letter sequence search run on the KJV, *Moby Dick* and the
  KJV's letters shuffled, each next to the count expected from letter frequencies alone.

One static page (`site/index.html`), no build step, no backend.

## Build the data

```bash
python3 scripts/build_data.py   # downloads sources to ~/.cache/versegraph, writes site/data/
python3 -m http.server -d site  # then open http://localhost:8000
```

## Sources and licenses

- Cross-references: [OpenBible.info](https://www.openbible.info/labs/cross-references/), CC BY
  (attribution required - kept in the page footer).
- KJV text: public domain, via [scrollmapper/bible_databases](https://github.com/scrollmapper/bible_databases).
- *Moby Dick*: public domain, Project Gutenberg #2701 (header and license text stripped).
- Code: MIT.

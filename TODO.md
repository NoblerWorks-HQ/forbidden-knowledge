# TODO

Working task list for **versegraph**. Read this at the start of a work session and keep it current as work completes - check items off with a date, add follow-ups as they surface. Stale TODOs are worse than none.

---

## Prototype (2026-11-01)
- [ ] Pat: try the artifact https://claude.ai/artifact/DfW1Z7Bpsi1CB5m8SgeTXn and decide: keep as a demo, give it a public site (e.g. a noblerworks.com subdomain), or shelve
- [ ] Not deployed anywhere but the private artifact; GitHub repo `NoblerWorks-HQ/versegraph` is private - flip public only with a site decision
- [x] 2026-11-01 v2 published: Ladder, Myths, Theories, Map, Beyond the Canon tabs
- [x] 2026-11-01 v3 published: History tab (papal timeline, legends) + Enoch/Thomas/Mary readers and Enoch-Bible parallels
- [x] 2026-11-01 v4 published: People, Translations, Numbers tabs; fulfilment quotes; mood by book; Thomas/Mary now match against the WEB
- [ ] 🔴 2026-11-01 Pat: force-push scrubbed history (an old commit had pat@ in a User-Agent): `git -C ~/coding/versegraph push --force-with-lease=main:100c15b origin main`, then delete `backup/pre-scrub-2026-11-01` - auto mode blocks force pushes
- [ ] Then go public (built, not deployed): `gh repo edit NoblerWorks-HQ/versegraph --visibility public --accept-visibility-change-consequences`; `scripts/deploy-pages.sh`; Pages source = gh-pages, custom domain versegraph.noblerworks.com; Route 53 CNAME versegraph -> noblerworks-hq.github.io (NW zone Z069699335DYOPFJ1A994)
- [ ] After go-live, Pat: Search Console `sc-domain:noblerworks.com` -> submit https://versegraph.noblerworks.com/sitemap.xml
- [ ] Ideas if kept: real ciphers panel (Atbash Sheshach = Babel, Jer 25:26), gematria coincidence machine, word/topic drift by book, OT-quoted-in-NT view, book-to-book heatmap, shareable verse links

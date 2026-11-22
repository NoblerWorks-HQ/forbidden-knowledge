#!/usr/bin/env bash
# Build the public site and publish it to the gh-pages branch (GitHub Pages serves it at
# forbidden.noblerworks.com). CI (.github/workflows/ci.yml) only checks; dist/ is built here and committed on top of gh-pages,
# replacing the previous site's files.
#
# Usage: scripts/deploy-pages.sh            # build + publish
#        scripts/deploy-pages.sh --dry-run  # build only, print what would be pushed
set -euo pipefail
cd "$(dirname "$0")/.."

# One row per real publish in the fleet deploy ledger (~/.cache/nw-deploy/ledger.jsonl), so
# `deploy-status forbidden-knowledge` shows it (engineering-standards deploy-script-standards
# "The deploy record"). Same row shape as the deploy kit's dk_* writer; this repo has no deploy kit.
DK_T0=$(date +%s); DK_STAGE=pre-ship; DK_CAUSE=""; DK_SHA=$(git rev-parse HEAD)
dk_row() {
  local rc=${1:-$?} status
  [ "$DK_STAGE" = none ] && return "$rc"
  case "$DK_STAGE:$rc" in
    verified:0) status=SUCCESS ;; shipped:*) status=UNVERIFIED; DK_CAUSE="${DK_CAUSE:-live index.html did not match dist/ within 5 min}" ;;
    pre-ship:*) status=FAILED ;; *) status=PARTIAL ;;
  esac
  mkdir -p "$HOME/.cache/nw-deploy" 2>/dev/null &&
    printf '{"v":1,"repo":"forbidden-knowledge","area":"pages","sha":"%s","start":"%s","secs":%s,"status":"%s","stage":"%s","exit":%s,"cause":"%s","root":"%s"}\n' \
      "$DK_SHA" "$(date -u -d "@$DK_T0" +%FT%TZ)" "$(( $(date +%s) - DK_T0 ))" "$status" "$DK_STAGE" "$rc" "$DK_CAUSE" "$PWD" \
      >> "$HOME/.cache/nw-deploy/ledger.jsonl" 2>/dev/null || true
  return "$rc"
}
trap dk_row EXIT

# Live sitemap saved before publishing, so the notifier can diff it against dist/ (IndexNow + Search Console)
SITEMAP_BEFORE="$(mktemp -t forbidden-sitemap-before.XXXXXX)"
node scripts/seo/notify-search-engines.mjs --snapshot "$SITEMAP_BEFORE" >/dev/null 2>&1 || { echo "WARN: could not snapshot the live sitemap - search engines will not be told what changed"; SITEMAP_BEFORE=""; }

python3 scripts/build_data.py
python3 scripts/build_site.py

if [[ "${1:-}" == "--dry-run" ]]; then
  DK_STAGE=none
  echo "dry run: dist/ built, nothing pushed"
  exit 0
fi

remote=$(git remote get-url origin)
rev=$(git rev-parse --short HEAD)
# A throwaway clone outside this checkout, so no hook or GIT_DIR from this repo applies.
# Each deploy is a normal commit on top of gh-pages (no force push).
tmp=$(mktemp -d "${HOME}/.cache/forbidden-knowledge-pages.XXXXXX")
trap 'dk_rc=$?; rm -rf "$tmp"; dk_row "$dk_rc"' EXIT
if git ls-remote --exit-code --heads "$remote" gh-pages >/dev/null; then
  git clone -q --depth 1 --branch gh-pages "$remote" "$tmp"
  git -C "$tmp" rm -q -r --ignore-unmatch .
else
  git -C "$tmp" init -q -b gh-pages
fi
cp -r dist/. "$tmp/"
git -C "$tmp" add -A
if git -C "$tmp" diff --cached --quiet; then
  echo "gh-pages already matches ${rev}; nothing to publish"
  DK_STAGE=none
  exit 0
fi
git -C "$tmp" -c user.name="$(git config user.name)" -c user.email="$(git config user.email)" \
  commit -q -m "Deploy site from ${rev}"
DK_STAGE=shipping
git -C "$tmp" push -q "$remote" HEAD:gh-pages
DK_STAGE=shipped
echo "published gh-pages from ${rev}; check https://forbidden.noblerworks.com/ in a minute"

# Verified = the live home page is byte-identical to the one just built (cache-busted, Pages takes a minute or two).
want=$(sha256sum dist/index.html | cut -d' ' -f1)
for _ in $(seq 1 30); do
  [ "$(curl -sf "https://forbidden.noblerworks.com/?v=${rev}-$RANDOM" | sha256sum | cut -d' ' -f1)" = "$want" ] && { DK_STAGE=verified; break; }
  sleep 10
done
[ "$DK_STAGE" = verified ] && echo "verified: live index.html matches dist/" || echo "WARN: live index.html still differs from dist/ after 5 min (UNVERIFIED in deploy-status)"

# Pages takes a minute or two to serve the new files; IndexNow checks the live key file first, so wait for it.
key=$(node -p 'require("./scripts/seo/notify-search-engines.config.json").indexNowKey')
for _ in $(seq 1 40); do curl -sf "https://forbidden.noblerworks.com/${key}.txt" | grep -q "$key" && break; sleep 6; done
# Loud on failure, never fails the deploy (the site is already live). Recovery: node scripts/seo/notify-search-engines.mjs --all
if [[ -n "$SITEMAP_BEFORE" ]]; then
  node scripts/seo/notify-search-engines.mjs --before "$SITEMAP_BEFORE" --after dist/sitemap.xml \
    || echo "WARN: search-engine notification failed - retry: node scripts/seo/notify-search-engines.mjs --all"
fi

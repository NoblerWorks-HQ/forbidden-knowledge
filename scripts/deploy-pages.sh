#!/usr/bin/env bash
# Build the public site and publish it to the gh-pages branch (GitHub Pages serves it at
# versegraph.noblerworks.com). No CI: dist/ is built here and committed on top of gh-pages,
# replacing the previous site's files.
#
# Usage: scripts/deploy-pages.sh            # build + publish
#        scripts/deploy-pages.sh --dry-run  # build only, print what would be pushed
set -euo pipefail
cd "$(dirname "$0")/.."

python3 scripts/build_data.py
python3 scripts/build_site.py

if [[ "${1:-}" == "--dry-run" ]]; then
  echo "dry run: dist/ built, nothing pushed"
  exit 0
fi

remote=$(git remote get-url origin)
rev=$(git rev-parse --short HEAD)
# A throwaway clone outside this checkout, so no hook or GIT_DIR from this repo applies.
# Each deploy is a normal commit on top of gh-pages (no force push).
tmp=$(mktemp -d "${HOME}/.cache/versegraph-pages.XXXXXX")
trap 'rm -rf "$tmp"' EXIT
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
  exit 0
fi
git -C "$tmp" -c user.name="$(git config user.name)" -c user.email="$(git config user.email)" \
  commit -q -m "Deploy site from ${rev}"
git -C "$tmp" push -q "$remote" HEAD:gh-pages
echo "published gh-pages from ${rev}; check https://versegraph.noblerworks.com/ in a minute"

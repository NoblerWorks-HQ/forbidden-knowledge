#!/usr/bin/env node
// notify-search-engines.mjs - tell search engines what a deploy changed.
//
// GENERATED - canonical source is
// engineering-standards/scripts/templates/notify-search-engines.mjs. Do not
// edit a stamped copy; change the template and re-stamp. Per-site values live
// beside this file in `notify-search-engines.config.json`.
//
// Standard: engineering-standards/search-indexing-standards.md (rules 2 and 3).
//
// Dependency-free on purpose (Node 22+, plus the AWS CLI v2 for the Search
// Console half): the first TypeScript notifiers each leaned on their repo's own
// tsx + google-auth-library, and a site that has neither should not grow three
// dev dependencies to ping a sitemap.
//
// Usage (from the repo root):
//   node scripts/seo/notify-search-engines.mjs --before <old.xml> --after <new.xml> [--dry-run]
//   node scripts/seo/notify-search-engines.mjs --all [--dry-run]
//   node scripts/seo/notify-search-engines.mjs --snapshot <out.xml>
//
//   --before   the live sitemap saved BEFORE the upload (deploy.sh does this)
//   --after    the sitemap the build produced. NOT the live one: the CDN keeps
//              serving the old copy until the invalidation lands, and a diff
//              against it finds nothing. May be a sitemap index; its children
//              are read from the same directory as `<name>.xml` files, or
//              fetched live when absent.
//              OMIT IT only when the sitemap is rendered at request time from a
//              database, so no build output exists (then the live sitemap is
//              the "after", and the deploy must invalidate the CDN first).
//   --all      every URL in the live sitemap (first run, or recovery)
//   --snapshot fetch the live sitemap (following an index) into one flat file
//
// When anything moved:
//   1. IndexNow (Bing, Yandex, Seznam, Naver - and through Bing, DuckDuckGo and
//      ChatGPT search) gets the added, updated and really-removed URLs.
//   2. Google Search Console re-reads the sitemap (PUT, then GET to confirm
//      `lastSubmitted` moved). Google has no supported "crawl this URL" API for
//      ordinary pages; a re-submitted sitemap with honest lastmod is the
//      documented signal. Skipped, and said so, when the config sets
//      `gscProperty` to null (a property that has not granted access).
// A deploy that changed nothing notifies nobody.
//
// Search Console auth is keyless: the AWS identity from `awsProfile` is
// exchanged for a Google token (Workload Identity Federation, pool
// `wifAudience`) that impersonates `reportingServiceAccount`, which must be a
// Full user on the property. Those identifiers live in the stamped repo's
// config, never in this template (house style: no account identifiers here).
//
// Config (`notify-search-engines.config.json`):
//   { "site": "https://example.com",            // origin, no trailing slash
//     "indexNowKey": "<32 hex>",                // served at /<key>.txt
//     "gscProperty": "sc-domain:example.com",   // or null to skip, with...
//     "gscSkipReason": "why it is skipped",
//     "awsProfile": "...", "awsRegion": "us-east-1",
//     "wifAudience": "//iam.googleapis.com/projects/<n>/locations/global/workloadIdentityPools/<pool>/providers/<provider>",
//     "reportingServiceAccount": "<sa>@<project>.iam.gserviceaccount.com" }
//
// Exit codes: 0 ok / nothing to do, 1 a notification failed, 2 usage.
// The caller (deploy.sh) prints a failure loudly and does NOT fail the deploy.

import { execFileSync } from "node:child_process";
import { createHash, createHmac } from "node:crypto";
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { basename, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const INDEXNOW_ENDPOINT = "https://api.indexnow.org/indexnow";
const INDEXNOW_BATCH = 10_000;
const GSC_BASE = "https://searchconsole.googleapis.com/webmasters/v3";
const GSC_SCOPE_WRITE = "https://www.googleapis.com/auth/webmasters";

// ---------- sitemap parsing (pure; exported for tests) ----------

const decodeXml = (s) =>
  s.replace(/&lt;/g, "<").replace(/&gt;/g, ">").replace(/&quot;/g, '"').replace(/&apos;/g, "'").replace(/&amp;/g, "&");
const encodeXml = (s) =>
  s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;").replace(/'/g, "&apos;");

/** URL -> lastmod ("" when absent) for a <urlset>. */
export function parseSitemap(xml) {
  const out = new Map();
  for (const block of xml.match(/<url>[\s\S]*?<\/url>/g) ?? []) {
    const loc = block.match(/<loc>\s*([^<]+?)\s*<\/loc>/)?.[1];
    if (!loc) continue;
    out.set(decodeXml(loc), block.match(/<lastmod>\s*([^<]+?)\s*<\/lastmod>/)?.[1] ?? "");
  }
  return out;
}

/** Child sitemap URLs of a <sitemapindex>; [] for a plain urlset. */
export function parseSitemapIndex(xml) {
  const out = [];
  for (const block of xml.match(/<sitemap>[\s\S]*?<\/sitemap>/g) ?? []) {
    const loc = block.match(/<loc>\s*([^<]+?)\s*<\/loc>/)?.[1];
    if (loc) out.push(decodeXml(loc));
  }
  return out;
}

export function renderFlatSitemap(entries) {
  const body = [...entries]
    .map(
      ([url, lastmod]) =>
        `  <url>\n    <loc>${encodeXml(url)}</loc>\n` + (lastmod ? `    <lastmod>${lastmod}</lastmod>\n` : "") + "  </url>",
    )
    .join("\n");
  return `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${body}\n</urlset>\n`;
}

export function diffSitemaps(before, after) {
  const added = [];
  const updated = [];
  const removed = [];
  for (const [url, lastmod] of after) {
    if (!before.has(url)) added.push(url);
    else if (before.get(url) !== lastmod) updated.push(url);
  }
  for (const url of before.keys()) if (!after.has(url)) removed.push(url);
  return { added, updated, removed };
}

// ---------- AWS SigV4 + Google WIF (exported for tests) ----------

const sha256 = (s) => createHash("sha256").update(s).digest("hex");
const hmac = (key, s) => createHmac("sha256", key).update(s).digest();

/**
 * The AWS "subject token" Google's STS accepts: a SigV4-signed
 * GetCallerIdentity request, serialized - never sent to AWS.
 */
export function awsSubjectToken({ accessKeyId, secretAccessKey, sessionToken }, audience, region, now = new Date()) {
  const host = `sts.${region}.amazonaws.com`;
  const query = "Action=GetCallerIdentity&Version=2011-06-15";
  const amzDate = now.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}/, "");
  const day = amzDate.slice(0, 8);
  const headers = { host, "x-amz-date": amzDate, "x-goog-cloud-target-resource": audience };
  if (sessionToken) headers["x-amz-security-token"] = sessionToken;
  const names = Object.keys(headers).sort();
  const canonical = [
    "POST",
    "/",
    query,
    names.map((n) => `${n}:${headers[n]}\n`).join(""),
    names.join(";"),
    sha256(""),
  ].join("\n");
  const scope = `${day}/${region}/sts/aws4_request`;
  const toSign = ["AWS4-HMAC-SHA256", amzDate, scope, sha256(canonical)].join("\n");
  const kSigning = hmac(hmac(hmac(hmac(`AWS4${secretAccessKey}`, day), region), "sts"), "aws4_request");
  const signature = createHmac("sha256", kSigning).update(toSign).digest("hex");
  headers.authorization = `AWS4-HMAC-SHA256 Credential=${accessKeyId}/${scope}, SignedHeaders=${names.join(";")}, Signature=${signature}`;
  const request = {
    url: `https://${host}?${query}`,
    method: "POST",
    headers: Object.entries(headers).map(([key, value]) => ({ key, value })),
  };
  return encodeURIComponent(JSON.stringify(request));
}

function awsCredentials(profile) {
  let raw;
  try {
    raw = execFileSync("aws", ["configure", "export-credentials", "--profile", profile, "--format", "process"], {
      encoding: "utf8",
      stdio: ["ignore", "pipe", "pipe"],
    });
  } catch (e) {
    throw new Error(`AWS credentials for profile "${profile}" unavailable: ${String(e.stderr || e.message).trim()}`);
  }
  const c = JSON.parse(raw);
  return { accessKeyId: c.AccessKeyId, secretAccessKey: c.SecretAccessKey, sessionToken: c.SessionToken };
}

export async function googleToken(cfg, scope) {
  const audience = cfg.wifAudience;
  const sa = cfg.reportingServiceAccount;
  const subject = awsSubjectToken(awsCredentials(cfg.awsProfile), audience, cfg.awsRegion || "us-east-1");
  const sts = await fetch("https://sts.googleapis.com/v1/token", {
    method: "POST",
    headers: { "content-type": "application/x-www-form-urlencoded" },
    body: new URLSearchParams({
      grant_type: "urn:ietf:params:oauth:grant-type:token-exchange",
      audience,
      scope: "https://www.googleapis.com/auth/cloud-platform",
      requested_token_type: "urn:ietf:params:oauth:token-type:access_token",
      subject_token_type: "urn:ietf:params:aws:token-type:aws4_request",
      subject_token: subject,
    }),
  });
  if (!sts.ok) throw new Error(`Google STS ${sts.status}: ${(await sts.text()).slice(0, 300)}`);
  const federated = (await sts.json()).access_token;
  const imp = await fetch(
    `https://iamcredentials.googleapis.com/v1/projects/-/serviceAccounts/${sa}:generateAccessToken`,
    {
      method: "POST",
      headers: { authorization: `Bearer ${federated}`, "content-type": "application/json" },
      body: JSON.stringify({ scope: [scope], lifetime: "600s" }),
    },
  );
  if (!imp.ok) throw new Error(`impersonating ${sa} ${imp.status}: ${(await imp.text()).slice(0, 300)}`);
  return (await imp.json()).accessToken;
}

// ---------- I/O ----------

const bust = (url) => `${url}${url.includes("?") ? "&" : "?"}cb=${Date.now()}`;

async function fetchText(url) {
  const r = await fetch(bust(url), { headers: { "cache-control": "no-cache" } });
  if (!r.ok) throw new Error(`GET ${url} -> ${r.status}`);
  return r.text();
}

/** A sitemap (index or urlset) as one URL -> lastmod map. A child that fails fails the read. */
async function readSitemap(xml, childSource) {
  const children = parseSitemapIndex(xml);
  if (children.length === 0) return parseSitemap(xml);
  const merged = new Map();
  for (const child of children) {
    for (const [u, m] of parseSitemap(await childSource(child))) merged.set(u, m);
  }
  return merged;
}

const liveSitemap = async (site) =>
  readSitemap(await fetchText(`${site}/sitemap.xml`), (child) => fetchText(child));

function builtSitemap(file) {
  if (!existsSync(file)) throw new Error(`--after file ${file} does not exist`);
  return readSitemap(readFileSync(file, "utf8"), async (child) => {
    const local = join(dirname(file), basename(new URL(child).pathname));
    return existsSync(local) ? readFileSync(local, "utf8") : fetchText(child);
  });
}

async function reallyGone(urls) {
  const checks = await Promise.all(
    urls.map(async (u) => {
      const r = await fetch(u, { method: "HEAD", redirect: "manual" }).catch(() => null);
      return r?.status === 200 ? null : u;
    }),
  );
  return checks.filter(Boolean);
}

async function indexNow(cfg, urls) {
  const keyLocation = `${cfg.site}/${cfg.indexNowKey}.txt`;
  const served = (await fetchText(keyLocation)).trim();
  if (served !== cfg.indexNowKey) throw new Error(`${keyLocation} does not serve the key (got ${served.slice(0, 40)})`);
  for (let i = 0; i < urls.length; i += INDEXNOW_BATCH) {
    const urlList = urls.slice(i, i + INDEXNOW_BATCH);
    const r = await fetch(INDEXNOW_ENDPOINT, {
      method: "POST",
      headers: { "content-type": "application/json; charset=utf-8" },
      body: JSON.stringify({ host: new URL(cfg.site).host, key: cfg.indexNowKey, keyLocation, urlList }),
    });
    if (r.status !== 200 && r.status !== 202) throw new Error(`IndexNow ${r.status}: ${(await r.text()).slice(0, 300)}`);
    console.log(`  IndexNow: ${urlList.length} URL(s) accepted (HTTP ${r.status})`);
  }
}

async function resubmitSitemap(cfg) {
  const token = await googleToken(cfg, GSC_SCOPE_WRITE);
  const url = `${GSC_BASE}/sites/${encodeURIComponent(cfg.gscProperty)}/sitemaps/${encodeURIComponent(`${cfg.site}/sitemap.xml`)}`;
  const put = await fetch(url, { method: "PUT", headers: { authorization: `Bearer ${token}` } });
  if (!put.ok) throw new Error(`Search Console sitemap submit ${put.status}: ${(await put.text()).slice(0, 300)}`);
  const entry = await (await fetch(url, { headers: { authorization: `Bearer ${token}` } })).json();
  const age = entry.lastSubmitted ? Date.now() - Date.parse(entry.lastSubmitted) : Infinity;
  if (!(age < 10 * 60_000)) throw new Error(`Search Console lastSubmitted did not move (${entry.lastSubmitted ?? "none"})`);
  console.log(`  Search Console: sitemap re-submitted (lastSubmitted ${entry.lastSubmitted})`);
}

export function loadConfig(file) {
  const cfg = JSON.parse(readFileSync(file, "utf8"));
  if (!/^https:\/\/[^/]+$/.test(cfg.site ?? "")) throw new Error(`${file}: "site" must be an https origin with no path`);
  if (!/^[0-9a-f]{32}$/.test(cfg.indexNowKey ?? "")) throw new Error(`${file}: "indexNowKey" must be 32 hex chars`);
  if (cfg.gscProperty !== null && typeof cfg.gscProperty !== "string")
    throw new Error(`${file}: "gscProperty" must be a property id or null`);
  if (cfg.gscProperty) {
    for (const k of ["awsProfile", "wifAudience", "reportingServiceAccount"]) {
      if (!cfg[k]) throw new Error(`${file}: "${k}" is required with gscProperty`);
    }
  }
  return cfg;
}

async function main() {
  const a = process.argv.slice(2);
  const val = (f) => (a.includes(f) ? a[a.indexOf(f) + 1] : undefined);
  const here = dirname(fileURLToPath(import.meta.url));
  const cfg = loadConfig(val("--config") ?? join(here, "notify-search-engines.config.json"));
  const snapshot = val("--snapshot");
  const before = val("--before");
  const after = val("--after");
  const all = a.includes("--all");
  const dryRun = a.includes("--dry-run");

  if (snapshot) {
    const live = await liveSitemap(cfg.site);
    if (live.size === 0) throw new Error(`${cfg.site}/sitemap.xml parsed to 0 URLs - refusing to save an empty snapshot`);
    writeFileSync(snapshot, renderFlatSitemap(live));
    console.log(`Saved ${live.size} live sitemap URLs to ${snapshot}`);
    return;
  }
  if (!all && !before) {
    console.error("usage: notify-search-engines.mjs --before <old.xml> [--after <new.xml>] | --all | --snapshot <out> [--dry-run]");
    process.exit(2);
  }

  // No --after: the sitemap is built at request time, so the live one IS the
  // result of this deploy. Everything else compares against the build output.
  const next = all || !after ? await liveSitemap(cfg.site) : await builtSitemap(after);
  if (next.size === 0) throw new Error(`${!all && after ? after : "the live sitemap"} parsed to 0 URLs - refusing to notify`);

  let urls;
  if (all) {
    urls = [...next.keys()];
    console.log(`Notifying all ${urls.length} sitemap URLs`);
  } else {
    if (!existsSync(before)) throw new Error(`--before file ${before} does not exist`);
    const prior = parseSitemap(readFileSync(before, "utf8"));
    if (prior.size === 0) throw new Error(`--before sitemap ${before} is empty; re-run with --all if intended`);
    const raw = diffSitemaps(prior, next);
    const diff = { ...raw, removed: await reallyGone(raw.removed) };
    urls = [...diff.added, ...diff.updated, ...diff.removed];
    console.log(
      `Sitemap: ${next.size} URLs; ${diff.added.length} added, ${diff.updated.length} updated, ${diff.removed.length} removed`,
    );
  }

  if (urls.length === 0) {
    console.log("No sitemap entry changed - nothing to notify.");
    return;
  }
  for (const u of urls.slice(0, 10)) console.log(`  ${u}`);
  if (urls.length > 10) console.log(`  ... and ${urls.length - 10} more`);
  if (dryRun) {
    console.log("--dry-run: not notifying.");
    return;
  }

  const failures = [];
  await indexNow(cfg, urls).catch((e) => failures.push(e.message));
  if (cfg.gscProperty) await resubmitSitemap(cfg).catch((e) => failures.push(e.message));
  else console.log(`  Search Console: skipped - ${cfg.gscSkipReason || "no property configured"}`);
  if (failures.length) {
    for (const f of failures) console.error(`  FAILED: ${f}`);
    process.exit(1);
  }
}

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  main().catch((e) => {
    console.error(`FAILED: ${e instanceof Error ? e.message : e}`);
    process.exit(1);
  });
}

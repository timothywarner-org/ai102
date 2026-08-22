#!/usr/bin/env node
/**
 * Build-RunbookHtml.mjs
 *
 * Render an AI-103 demo runbook Markdown file into a self-contained, single-file
 * HTML page tuned for reading at the recording desk.
 *
 * WHY a generator instead of hand-written HTML: the runbooks are living documents
 * (L11 still carries an open A2A blocker), so a one-time conversion rots on the
 * first edit. Re-run this and the page is current again.
 *
 * WHY a custom renderer instead of a Markdown library: the value is in the parts a
 * generic converter throws away. [DO] / [SAY] / [VERIFY] become labeled badges, and
 * every numbered beat ("**2.17** [VERIFY] ...") becomes a card that owns the code
 * blocks and tables that follow it. Zero dependencies also means no install step on
 * a machine mid-recording.
 *
 * Accessibility contract (non-negotiable for this author):
 *   - No color-only signaling. Every badge carries a text label and a glyph.
 *   - Large default type, generous line height, high contrast in light and dark.
 *
 * USAGE
 *   node Build-RunbookHtml.mjs <input.md> [<input2.md> ...]
 *   node Build-RunbookHtml.mjs --all          # every *-demo-runbook.md beside this script
 *
 * OUTPUT
 *   <same folder>/<same basename>.html
 */

import { readFileSync, writeFileSync, readdirSync } from 'node:fs';
import { basename, dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const SCRIPT_DIR = dirname(fileURLToPath(import.meta.url));

/* ------------------------------------------------------------------ *
 * Inline rendering
 * ------------------------------------------------------------------ */

const escapeHtml = (s) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');

/** Tags we promote to badges. Longest-first so "VERIFY IN PORTAL" wins over "VERIFY". */
const TAGS = {
  'VERIFY IN PORTAL': { cls: 'portal', glyph: '?' },
  DO: { cls: 'do', glyph: '▶' },
  SAY: { cls: 'say', glyph: '“' },
  VERIFY: { cls: 'verify', glyph: '✓' },
  PAUSE: { cls: 'pause', glyph: '⏸' },
};
const TAG_RE = /\[(VERIFY IN PORTAL|DO|SAY|VERIFY|PAUSE)\]/g;

function badge(name) {
  const t = TAGS[name];
  return `<span class="tag tag-${t.cls}"><span class="tag-glyph" aria-hidden="true">${t.glyph}</span>${name}</span>`;
}

/**
 * Inline Markdown. Code spans are pulled out first so that asterisks and pipes
 * inside paths (l10-*, knowledge\*.md) never get read as emphasis.
 */
function inline(src) {
  const codes = [];
  let s = escapeHtml(src);

  // An ASCII sentinel, not a bare number: prose here is full of loose digits
  // ("12 succeeded, 6 failed") and a looser placeholder would eat them on restore.
  s = s.replace(/`([^`]+)`/g, (_m, c) => {
    codes.push(c);
    return `@@CODE${codes.length - 1}@@`;
  });

  s = s.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
  s = s.replace(/(?<![\w*])\*([^*\n]+)\*(?![\w*])/g, '<em>$1</em>');

  // Autolinks arrive pre-escaped, so match the entity form.
  s = s.replace(/&lt;(https?:\/\/[^\s&]+)&gt;/g, '<a href="$1" target="_blank" rel="noopener">$1</a>');
  s = s.replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');

  s = s.replace(TAG_RE, (_m, name) => badge(name));

  return s.replace(/@@CODE(\d+)@@/g, (_m, i) => `<code>${codes[Number(i)]}</code>`);
}

const slug = (s) =>
  s
    .toLowerCase()
    .replace(/`/g, '')
    .replace(/[^a-z0-9]+/g, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 60);

/* ------------------------------------------------------------------ *
 * Block parsing
 * ------------------------------------------------------------------ */

const isFence = (l) => /^\s*```/.test(l);
const isHeading = (l) => /^#{1,6}\s/.test(l);
const isRule = (l) => /^---+\s*$/.test(l);
const isTableRow = (l) => /^\s*\|/.test(l);
const isQuote = (l) => /^\s*>/.test(l);
const isBullet = (l) => /^\s*[-*]\s+/.test(l);
const isOrdered = (l) => /^\s*\d+[a-zA-Z]?\.\s+/.test(l);
const BEAT_RE = /^\*\*(\d+\.[0-9A-Za-z]*)\*\*\s*(.*)$/;

/**
 * Split raw lines into typed blocks. Fences are opaque so blank lines and pipes
 * inside a code sample never split a block.
 */
function tokenize(lines) {
  const blocks = [];
  let i = 0;

  while (i < lines.length) {
    const line = lines[i];

    if (!line.trim()) {
      i++;
      continue;
    }

    if (isFence(line)) {
      const lang = line.trim().replace(/^```/, '').trim();
      const body = [];
      i++;
      while (i < lines.length && !isFence(lines[i])) body.push(lines[i++]);
      i++; // closing fence
      blocks.push({ type: 'code', lang, body });
      continue;
    }

    if (isHeading(line)) {
      const m = line.match(/^(#{1,6})\s+(.*)$/);
      blocks.push({ type: 'heading', level: m[1].length, text: m[2].trim() });
      i++;
      continue;
    }

    if (isRule(line)) {
      blocks.push({ type: 'rule' });
      i++;
      continue;
    }

    if (isTableRow(line)) {
      const rows = [];
      while (i < lines.length && isTableRow(lines[i])) rows.push(lines[i++]);
      blocks.push({ type: 'table', rows });
      continue;
    }

    if (isQuote(line)) {
      const body = [];
      while (i < lines.length && (isQuote(lines[i]) || (body.length && lines[i].trim() && !isHeading(lines[i])))) {
        if (!isQuote(lines[i])) break;
        body.push(lines[i++].replace(/^\s*>\s?/, ''));
      }
      blocks.push({ type: 'quote', body });
      continue;
    }

    if (isOrdered(line) || isBullet(line)) {
      const ordered = isOrdered(line);
      const items = [];
      let fenced = false;

      while (i < lines.length) {
        const l = lines[i];
        const starts = ordered ? isOrdered(l) : isBullet(l);

        if (!fenced && starts) {
          const marker = l.match(ordered ? /^\s*(\d+[a-zA-Z]?)\.\s+/ : /^\s*[-*]\s+/);
          items.push({ label: ordered ? marker[1] : null, body: [l.slice(marker[0].length)] });
          if (isFence(l.slice(marker[0].length))) fenced = true;
          i++;
          continue;
        }
        if (!items.length) break;

        // Continuation: indented text, or a blank line followed by more indented text.
        if (fenced) {
          if (isFence(l)) fenced = false;
          items[items.length - 1].body.push(l.replace(/^ {0,3}/, ''));
          i++;
          continue;
        }
        if (!l.trim()) {
          const next = lines[i + 1] ?? '';
          const continues = /^\s{2,}\S/.test(next) || (ordered ? isOrdered(next) : isBullet(next));
          if (!continues) break;
          items[items.length - 1].body.push('');
          i++;
          continue;
        }
        if (/^\s{2,}\S/.test(l)) {
          const dedented = l.replace(/^\s{0,3}/, '');
          if (isFence(dedented)) fenced = true;
          items[items.length - 1].body.push(dedented);
          i++;
          continue;
        }
        break;
      }
      blocks.push({ type: 'list', ordered, items });
      continue;
    }

    // Paragraph: run to the next blank line or structural marker.
    const para = [];
    while (
      i < lines.length &&
      lines[i].trim() &&
      !isFence(lines[i]) &&
      !isHeading(lines[i]) &&
      !isRule(lines[i]) &&
      !isTableRow(lines[i]) &&
      !isQuote(lines[i])
    ) {
      if (para.length && (isOrdered(lines[i]) || isBullet(lines[i]))) break;
      para.push(lines[i++]);
    }
    blocks.push({ type: 'para', body: para });
  }

  return blocks;
}

/* ------------------------------------------------------------------ *
 * Block rendering
 * ------------------------------------------------------------------ */

function renderTable(rows) {
  const cells = (row) =>
    row
      .trim()
      .replace(/^\|/, '')
      .replace(/\|$/, '')
      .split('|')
      .map((c) => c.trim());

  const head = cells(rows[0]);
  const body = rows.slice(2).map(cells);

  const thead = `<thead><tr>${head.map((c) => `<th>${inline(c)}</th>`).join('')}</tr></thead>`;
  const tbody = `<tbody>${body
    .map((r) => `<tr>${r.map((c) => `<td>${inline(c)}</td>`).join('')}</tr>`)
    .join('')}</tbody>`;

  return `<div class="table-wrap"><table>${thead}${tbody}</table></div>`;
}

function quoteFlavor(text) {
  const t = text.toUpperCase();
  if (t.includes('WARNING') || t.includes('BLOCKER')) return { cls: 'warn', label: 'Warning' };
  if (t.startsWith('OBJECTIVE:')) return { cls: 'objective', label: 'Objective' };
  if (t.includes('SHOOTING NOTE') || t.includes('READ THIS') || t.includes('MONEY BEAT'))
    return { cls: 'shoot', label: 'Shooting note' };
  if (t.includes('INGESTION GATE')) return { cls: 'shoot', label: 'Gate' };
  return { cls: 'note', label: 'Note' };
}

/** Which badge a beat leads with, used for the card's left rail label. */
function beatKind(text) {
  const m = text.match(/\[(VERIFY IN PORTAL|DO|SAY|VERIFY)\]/);
  if (!m) return 'plain';
  return TAGS[m[1]].cls;
}

/**
 * A beat's text wraps mid-sentence in the source. Rejoin it, but start a new
 * visual line wherever a bracket tag begins one, so [VERIFY] never buries itself
 * at the tail of a [DO] sentence.
 */
function beatLines(rawLines) {
  const out = [];
  for (const l of rawLines) {
    if (out.length && !/^\[/.test(l.trim())) out[out.length - 1] += ' ' + l.trim();
    else out.push(l.trim());
  }
  return out;
}

function renderBlocks(blocks, toc) {
  const html = [];
  let i = 0;

  while (i < blocks.length) {
    const b = blocks[i];

    if (b.type === 'heading') {
      const id = slug(b.text);
      if (b.level <= 3) toc.push({ level: b.level, text: b.text, id });
      html.push(`<h${b.level} id="${id}">${inline(b.text)}</h${b.level}>`);
      i++;
      continue;
    }

    if (b.type === 'rule') {
      html.push('<hr>');
      i++;
      continue;
    }

    if (b.type === 'code') {
      html.push(
        `<pre class="code${b.lang ? ' lang-' + slug(b.lang) : ''}"${
          b.lang ? ` data-lang="${escapeHtml(b.lang)}"` : ''
        }><code>${escapeHtml(b.body.join('\n'))}</code></pre>`
      );
      i++;
      continue;
    }

    if (b.type === 'table') {
      html.push(renderTable(b.rows));
      i++;
      continue;
    }

    if (b.type === 'quote') {
      const text = b.body.join(' ').replace(/\*\*/g, '').trim();
      const f = quoteFlavor(text);
      const inner = renderBlocks(tokenize(b.body), []);
      html.push(
        `<aside class="callout callout-${f.cls}"><p class="callout-label">${f.label}</p>${inner}</aside>`
      );
      i++;
      continue;
    }

    if (b.type === 'list') {
      const tag = b.ordered ? 'ol' : 'ul';
      const items = b.items
        .map((it) => {
          const inner = renderBlocks(tokenize(it.body), []);
          const val = it.label ? ` data-label="${escapeHtml(it.label)}."` : '';
          return `<li${val}>${inner}</li>`;
        })
        .join('');
      html.push(`<${tag} class="${b.ordered ? 'steps' : 'bullets'}">${items}</${tag}>`);
      i++;
      continue;
    }

    // Paragraph, or a beat card.
    const first = b.body[0].trim();

    if (/^\*\*\[PAUSE\]\*\*$/.test(first)) {
      html.push('<div class="pause-bar"><span aria-hidden="true">⏸</span> PAUSE</div>');
      i++;
      continue;
    }

    const beat = first.match(BEAT_RE);
    if (beat) {
      const [, id, rest] = beat;
      const lines = beatLines([rest, ...b.body.slice(1)]).filter(Boolean);
      const kind = beatKind(lines.join(' '));

      // Absorb the blocks that belong to this beat: its code, its table, its
      // follow-on [SAY]. Stop at the next beat, heading, rule, or pause.
      i++;
      const owned = [];
      while (i < blocks.length) {
        const n = blocks[i];
        if (n.type === 'heading' || n.type === 'rule') break;
        if (n.type === 'para') {
          const t = n.body[0].trim();
          if (BEAT_RE.test(t) || /^\*\*\[PAUSE\]\*\*$/.test(t)) break;
        }
        owned.push(blocks[i++]);
      }

      const bodyHtml =
        lines.map((l) => `<p class="beat-line">${inline(l)}</p>`).join('') +
        (owned.length ? renderBlocks(owned, toc) : '');

      html.push(
        `<section class="beat beat-${kind}" id="beat-${slug(id)}">` +
          `<div class="beat-head">` +
          `<label class="beat-check"><input type="checkbox" data-beat="${escapeHtml(id)}"><span class="beat-id">${escapeHtml(
            id
          )}</span></label>` +
          `</div>` +
          `<div class="beat-body">${bodyHtml}</div>` +
          `</section>`
      );
      continue;
    }

    html.push(`<p>${inline(b.body.join(' '))}</p>`);
    i++;
  }

  return html.join('\n');
}

/* ------------------------------------------------------------------ *
 * Page shell
 * ------------------------------------------------------------------ */

const CSS = `
:root{
  --bg:#f7f8fa; --panel:#ffffff; --ink:#16191f; --muted:#5b6472; --line:#dde1e8;
  --code-bg:#eef1f6; --code-ink:#1c2330; --accent:#1f4fd8; --accent-soft:#e6ecfd;
  --do-bg:#e4ecff; --do-ink:#123a9c; --do-rail:#2a5adb;
  --say-bg:#efe7fb; --say-ink:#4b2a8c; --say-rail:#7a4fd0;
  --ver-bg:#e2f1ea; --ver-ink:#14543a; --ver-rail:#2e8b63;
  --por-bg:#fdf0da; --por-ink:#6d4708; --por-rail:#c1841c;
  --warn-bg:#fdf0da; --warn-rail:#c1841c;
  --radius:10px;
  --fs:19px;
}
@media (prefers-color-scheme: dark){
  :root{
    --bg:#12151b; --panel:#191d25; --ink:#e8ecf3; --muted:#a2acbc; --line:#2c333f;
    --code-bg:#11151c; --code-ink:#dbe3f0; --accent:#7ea2ff; --accent-soft:#1d2740;
    --do-bg:#1b2949; --do-ink:#b9cdff; --do-rail:#4d7bea;
    --say-bg:#2a1f45; --say-ink:#d5c2ff; --say-rail:#9a76e6;
    --ver-bg:#14301f; --ver-ink:#a9e3c4; --ver-rail:#48b184;
    --por-bg:#3a2c11; --por-ink:#f0cd8c; --por-rail:#d6a03c;
    --warn-bg:#3a2c11; --warn-rail:#d6a03c;
  }
}
*{box-sizing:border-box}
html{scroll-behavior:smooth;scroll-padding-top:5.5rem}
body{
  margin:0;background:var(--bg);color:var(--ink);
  font:var(--fs)/1.7 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,sans-serif;
  -webkit-font-smoothing:antialiased;
}
code,pre,kbd{font-family:"Cascadia Code",Consolas,"SF Mono",Menlo,monospace}

/* Top bar ------------------------------------------------------------ */
.topbar{
  position:sticky;top:0;z-index:50;background:var(--panel);
  border-bottom:1px solid var(--line);padding:.6rem 1.2rem;
  display:flex;gap:1rem;align-items:center;flex-wrap:wrap;
}
.topbar h1{font-size:1.05rem;margin:0;font-weight:700;letter-spacing:.01em}
.topbar .sub{color:var(--muted);font-size:.82rem;margin:0}
.spacer{flex:1}
.ctrl{
  border:1px solid var(--line);background:transparent;color:var(--ink);
  border-radius:8px;padding:.3rem .7rem;font-size:.82rem;cursor:pointer;font-weight:600;
}
.ctrl:hover{background:var(--accent-soft);border-color:var(--accent)}
.progress{font-size:.82rem;color:var(--muted);font-variant-numeric:tabular-nums}

/* Layout ------------------------------------------------------------- */
.shell{display:grid;grid-template-columns:1fr;gap:0;max-width:1500px;margin:0 auto}
@media (min-width:1150px){
  .shell{grid-template-columns:290px minmax(0,1fr);}
  .toc{display:block}
}
.toc{
  display:none;position:sticky;top:4.2rem;align-self:start;
  max-height:calc(100vh - 5rem);overflow:auto;padding:1.5rem 1rem 3rem;
  font-size:.85rem;line-height:1.45;border-right:1px solid var(--line);
}
.toc a{display:block;color:var(--muted);text-decoration:none;padding:.28rem .5rem;border-radius:6px}
.toc a:hover{background:var(--accent-soft);color:var(--ink)}
.toc a.lvl1{font-weight:700;color:var(--ink);margin-top:.7rem}
.toc a.lvl2{font-weight:600}
.toc a.lvl3{padding-left:1.2rem;font-size:.8rem}
main{padding:1.8rem 1.6rem 6rem;max-width:82ch}

/* Typography --------------------------------------------------------- */
h1,h2,h3,h4{line-height:1.25;margin:2.2rem 0 .8rem}
main>h1{
  font-size:1.75rem;padding:.9rem 0 .5rem;border-top:3px solid var(--accent);
  margin-top:3rem;
}
main>h1:first-child{margin-top:0;border-top:none}
h2{font-size:1.3rem;border-bottom:1px solid var(--line);padding-bottom:.35rem}
h3{font-size:1.08rem;color:var(--accent)}
p{margin:.65rem 0}
a{color:var(--accent)}
hr{border:none;border-top:1px dashed var(--line);margin:2.4rem 0}
strong{font-weight:700}

/* Tags --------------------------------------------------------------- */
.tag{
  display:inline-flex;align-items:center;gap:.32em;
  font-size:.72em;font-weight:800;letter-spacing:.06em;
  padding:.12em .5em;border-radius:5px;margin-right:.35em;
  vertical-align:.08em;white-space:nowrap;
}
.tag-glyph{font-weight:400}
.tag-do{background:var(--do-bg);color:var(--do-ink)}
.tag-say{background:var(--say-bg);color:var(--say-ink)}
.tag-verify{background:var(--ver-bg);color:var(--ver-ink)}
.tag-portal{background:var(--por-bg);color:var(--por-ink)}
.tag-pause{background:var(--accent-soft);color:var(--accent)}

/* Beats -------------------------------------------------------------- */
.beat{
  display:grid;grid-template-columns:3.4rem minmax(0,1fr);gap:.9rem;
  background:var(--panel);border:1px solid var(--line);border-left:5px solid var(--muted);
  border-radius:var(--radius);padding:.85rem 1rem;margin:.85rem 0;
}
.beat-do{border-left-color:var(--do-rail)}
.beat-say{border-left-color:var(--say-rail)}
.beat-verify{border-left-color:var(--ver-rail)}
.beat-portal{border-left-color:var(--por-rail)}
.beat-check{display:flex;flex-direction:column;align-items:center;gap:.3rem;cursor:pointer}
.beat-check input{width:1.15rem;height:1.15rem;cursor:pointer;accent-color:var(--accent)}
.beat-id{
  font:700 .95rem/1 "Cascadia Code",Consolas,monospace;color:var(--muted);
  font-variant-numeric:tabular-nums;
}
.beat-body>*:first-child{margin-top:0}
.beat-body>*:last-child{margin-bottom:0}
.beat-line{margin:.3rem 0}
.beat.done{opacity:.5}
.beat.done .beat-body{text-decoration:line-through;text-decoration-thickness:1px}

.pause-bar{
  display:flex;align-items:center;justify-content:center;gap:.6rem;
  background:var(--accent-soft);color:var(--accent);font-weight:800;letter-spacing:.18em;
  border-radius:var(--radius);padding:.65rem;margin:1.6rem 0;font-size:.85rem;
}

/* Code --------------------------------------------------------------- */
pre.code{
  background:var(--code-bg);color:var(--code-ink);border:1px solid var(--line);
  border-radius:var(--radius);padding:.85rem 1rem;overflow-x:auto;
  font-size:.86em;line-height:1.55;margin:.8rem 0;position:relative;
}
pre.code[data-lang]::before{
  content:attr(data-lang);position:absolute;top:0;right:0;
  background:var(--line);color:var(--muted);font-size:.68rem;font-weight:700;
  padding:.1rem .5rem;border-radius:0 var(--radius) 0 6px;letter-spacing:.08em;text-transform:uppercase;
}
code{background:var(--code-bg);padding:.1em .35em;border-radius:4px;font-size:.88em}
pre code{background:none;padding:0;font-size:1em}

/* Tables ------------------------------------------------------------- */
.table-wrap{overflow-x:auto;margin:1rem 0;border:1px solid var(--line);border-radius:var(--radius)}
table{border-collapse:collapse;width:100%;font-size:.88em}
th,td{text-align:left;padding:.55rem .8rem;border-bottom:1px solid var(--line);vertical-align:top}
th{background:var(--accent-soft);font-weight:700;white-space:nowrap}
tbody tr:last-child td{border-bottom:none}
tbody tr:nth-child(even){background:color-mix(in srgb,var(--line) 25%,transparent)}

/* Callouts ----------------------------------------------------------- */
.callout{
  border:1px solid var(--line);border-left:5px solid var(--accent);
  background:var(--panel);border-radius:var(--radius);padding:.8rem 1rem;margin:1.1rem 0;
}
.callout-label{
  margin:0 0 .35rem;font-size:.7rem;font-weight:800;letter-spacing:.12em;
  text-transform:uppercase;color:var(--muted);
}
.callout-warn{border-left-color:var(--warn-rail);background:var(--warn-bg)}
.callout-shoot{border-left-color:var(--say-rail)}
.callout-objective{border-left-color:var(--ver-rail)}
.callout p:last-child{margin-bottom:0}

/* Lists -------------------------------------------------------------- */
ol.steps{list-style:none;counter-reset:none;padding-left:0;margin:1rem 0}
ol.steps>li{
  position:relative;padding-left:3rem;margin:.7rem 0;min-height:1.6rem;
}
ol.steps>li::before{
  content:attr(data-label);position:absolute;left:0;top:.1rem;
  font:700 .85rem/1.5 "Cascadia Code",Consolas,monospace;color:var(--accent);
  font-variant-numeric:tabular-nums;
}
ul.bullets{padding-left:1.3rem}
ul.bullets li{margin:.35rem 0}
li>p:first-child{margin-top:0}
li>p:last-child{margin-bottom:0}

/* Print -------------------------------------------------------------- */
@media print{
  :root{--fs:11pt}
  .topbar,.toc{display:none !important}
  .shell{grid-template-columns:1fr}
  main{max-width:none;padding:0}
  body{background:#fff}
  main>h1{break-before:page}
  main>h1:first-child{break-before:avoid}
  .beat,.callout,pre.code,.table-wrap{break-inside:avoid}
  a[href^="http"]::after{content:" (" attr(href) ")";font-size:.8em;color:#555}
}
`;

const JS = `
(function () {
  var KEY = 'runbook:' + document.body.dataset.doc;
  var boxes = Array.prototype.slice.call(document.querySelectorAll('input[data-beat]'));
  var counter = document.getElementById('progress');
  var saved = {};
  try { saved = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) { saved = {}; }

  function paint(box) {
    box.closest('.beat').classList.toggle('done', box.checked);
  }
  function count() {
    var n = boxes.filter(function (b) { return b.checked; }).length;
    counter.textContent = n + ' / ' + boxes.length + ' beats';
  }
  function persist() {
    var out = {};
    boxes.forEach(function (b) { if (b.checked) out[b.dataset.beat] = 1; });
    try { localStorage.setItem(KEY, JSON.stringify(out)); } catch (e) {}
  }

  boxes.forEach(function (b) {
    if (saved[b.dataset.beat]) b.checked = true;
    paint(b);
    b.addEventListener('change', function () { paint(b); count(); persist(); });
  });
  count();

  document.getElementById('reset').addEventListener('click', function () {
    boxes.forEach(function (b) { b.checked = false; paint(b); });
    count(); persist();
  });

  // Font stepper. Recording desks sit further from the screen than a dev desk.
  var size = Number(localStorage.getItem(KEY + ':fs') || 19);
  function applySize() {
    document.documentElement.style.setProperty('--fs', size + 'px');
    try { localStorage.setItem(KEY + ':fs', String(size)); } catch (e) {}
  }
  applySize();
  document.getElementById('bigger').addEventListener('click', function () {
    size = Math.min(30, size + 1); applySize();
  });
  document.getElementById('smaller').addEventListener('click', function () {
    size = Math.max(14, size - 1); applySize();
  });

  // Highlight the section currently on screen in the table of contents.
  var links = {};
  Array.prototype.forEach.call(document.querySelectorAll('.toc a'), function (a) {
    links[a.getAttribute('href').slice(1)] = a;
  });
  var heads = Array.prototype.slice.call(document.querySelectorAll('main h1[id],main h2[id],main h3[id]'));
  var io = new IntersectionObserver(function (entries) {
    entries.forEach(function (en) {
      var a = links[en.target.id];
      if (a) a.style.background = en.isIntersecting ? 'var(--accent-soft)' : '';
    });
  }, { rootMargin: '-10% 0px -80% 0px' });
  heads.forEach(function (h) { io.observe(h); });
})();
`;

function buildPage(md, docId) {
  const lines = md.replace(/\r\n/g, '\n').split('\n');
  const blocks = tokenize(lines);

  // Title and subtitle come off the top of the document, then get dropped from
  // the body so the sticky bar owns them.
  let title = 'Demo runbook';
  let subtitle = '';
  if (blocks[0]?.type === 'heading' && blocks[0].level === 1) {
    title = blocks[0].text;
    blocks.shift();
  }
  if (blocks[0]?.type === 'para' && /^\*\*.*\*\*$/.test(blocks[0].body.join(' ').trim())) {
    subtitle = blocks[0].body.join(' ').replace(/\*\*/g, '').trim();
    blocks.shift();
  }

  const toc = [];
  const body = renderBlocks(blocks, toc);

  const tocHtml = toc
    .map((t) => `<a class="lvl${t.level}" href="#${t.id}">${inline(t.text)}</a>`)
    .join('\n');

  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>${escapeHtml(title)}</title>
<style>${CSS}</style>
</head>
<body data-doc="${escapeHtml(docId)}">
<header class="topbar">
  <div>
    <h1>${inline(title)}</h1>
    ${subtitle ? `<p class="sub">${inline(subtitle)}</p>` : ''}
  </div>
  <div class="spacer"></div>
  <span class="progress" id="progress">0 beats</span>
  <button class="ctrl" id="smaller" title="Smaller text">A-</button>
  <button class="ctrl" id="bigger" title="Larger text">A+</button>
  <button class="ctrl" id="reset" title="Clear all beat checkmarks">Reset</button>
  <button class="ctrl" onclick="window.print()" title="Print or save as PDF">Print</button>
</header>
<div class="shell">
  <nav class="toc" aria-label="Runbook contents">${tocHtml}</nav>
  <main>${body}</main>
</div>
<script>${JS}</script>
</body>
</html>
`;
}

/* ------------------------------------------------------------------ *
 * CLI
 * ------------------------------------------------------------------ */

function main() {
  const args = process.argv.slice(2);
  let inputs = args.filter((a) => !a.startsWith('--'));

  if (args.includes('--all') || inputs.length === 0) {
    inputs = readdirSync(SCRIPT_DIR)
      .filter((f) => /-demo-runbook\.md$/i.test(f))
      .map((f) => join(SCRIPT_DIR, f));
  }

  if (inputs.length === 0) {
    console.error('No *-demo-runbook.md files found. Pass a path explicitly.');
    process.exitCode = 1;
    return;
  }

  for (const input of inputs) {
    const src = resolve(input);
    let md;
    try {
      md = readFileSync(src, 'utf8');
    } catch (err) {
      console.error(`SKIP ${basename(src)}: ${err.message}`);
      process.exitCode = 1;
      continue;
    }
    const out = src.replace(/\.md$/i, '.html');
    const docId = basename(src, '.md');
    writeFileSync(out, buildPage(md, docId), 'utf8');
    const beats = (readFileSync(out, 'utf8').match(/class="beat beat-/g) || []).length;
    console.log(`OK   ${basename(out)}  (${beats} beats)`);
  }
}

main();

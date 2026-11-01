// Renders Mermaid flowcharts to SVG and PNG files: Mermaid 10.9.1 (vendor/mermaid.min.js)
// in headless Chromium through Playwright, the way the prototype pictures were made.
//   node render.js MERMAID_JS < jobs.json        jobs: [{"mmd": text, "svg": path, "png": path}]
// Prints one JSON line: {"results": [{"ok": true, "width", "height"} | {"error": text}]},
// or {"error": text} when the renderer itself cannot run.
'use strict';
const fs = require('fs');

function done(obj) { process.stdout.write(JSON.stringify(obj) + '\n'); }
function first(e) { return String((e && e.message) || e).split('\n')[0]; }

let chromium;
try {
  ({ chromium } = require('playwright'));
} catch (e) {
  done({ error: 'node cannot load playwright (' + first(e) + ')' });
  process.exit(0);
}

(async () => {
  const mermaidJs = process.argv[2];
  const jobs = JSON.parse(fs.readFileSync(0, 'utf8'));
  let browser;
  try {
    browser = await chromium.launch();
  } catch (e) {
    done({ error: 'headless Chromium does not start (' + first(e) + ')' });
    return;
  }
  const results = [];
  try {
    const page = await browser.newPage({ viewport: { width: 1400, height: 600 } });
    await page.setContent('<!doctype html><html><head><meta charset="utf-8"></head>' +
      '<body style="background:#fff;margin:0"><div id="out" style="display:inline-block"></div></body></html>');
    await page.addScriptTag({ path: mermaidJs });
    await page.evaluate(() => mermaid.initialize({ startOnLoad: false, securityLevel: 'strict',
      flowchart: { htmlLabels: true } }));
    for (let n = 0; n < jobs.length; n++) {
      const job = jobs[n];
      try {
        const got = await page.evaluate(async ({ code, id }) => {
          const out = document.getElementById('out');
          out.innerHTML = '';
          const { svg } = await mermaid.render(id, code);
          out.innerHTML = svg;
          const el = out.querySelector('svg');
          const vb = el.viewBox.baseVal;
          const w = Math.ceil(vb.width), h = Math.ceil(vb.height);
          el.style.maxWidth = 'none';             // natural size, not shrunk to the pane
          el.setAttribute('width', String(w));
          el.setAttribute('height', String(h));
          return { w, h, xml: new XMLSerializer().serializeToString(el) };
        }, { code: job.mmd, id: 'fg' + n });
        await page.setViewportSize({ width: Math.max(1400, got.w + 20), height: Math.max(600, got.h + 20) });
        fs.writeFileSync(job.svg, '<?xml version="1.0" encoding="UTF-8"?>\n' + got.xml + '\n');
        const el = await page.$('#out svg');
        await el.screenshot({ path: job.png });
        results.push({ ok: true, width: got.w, height: got.h });
      } catch (e) {
        results.push({ error: first(e) });
      }
    }
  } finally {
    await browser.close();
  }
  done({ results });
})().catch((e) => done({ error: first(e) }));

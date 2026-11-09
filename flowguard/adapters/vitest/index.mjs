// FlowGuard vitest adapter (minimal: vitest, ESM only). Python (`python -m flowguard.intent.vitest prepare`)
// writes a plan: which functions to observe, their parameter names, representative values, same-name copies
// and the baseline sources. This plugin only edits text: after each planned function it adds
// `f = wrap(f)` (a `const f = ...` becomes `let`), and it loads a baseline source as the virtual module
// `<file>?flowguard-baseline`, so relative imports resolve from the same folder. The judgments are Python's.
// It also adds FlowGuard's own test project (session.test.mjs), run after the project's tests
// (sequence.groupOrder): its one test case fails on a red, so the red is in vitest's results (JSON, junit) too.
import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const RUNTIME = path.join(HERE, 'runtime.mjs');
const GLOBAL_SETUP = path.join(HERE, 'global-setup.mjs');
const SESSION = 'session.test.mjs';
const LAST = 1000;               // the session project's group comes after the others (vitest spreads its groups: keep it small)
const BASELINE = '?flowguard-baseline';
const PREFIX = 'virtual:flowguard/';

// One spelling of a file for plan lookups: forward slashes, no query, a lower-case drive letter on Windows.
export function normalize(file, windows = process.platform === 'win32') {
  let text = String(file).split('?')[0].replace(/\\/g, '/');
  if (text.startsWith('/@fs/')) text = text.slice(4);
  if (windows && /^\/[A-Za-z]:\//.test(text)) text = text.slice(1);
  if (windows && /^[A-Za-z]:\//.test(text)) text = text[0].toLowerCase() + text.slice(1);
  return windows ? text.toLowerCase() : text;
}

export function flowguardPlugin({ plan: planFile, python, root }) {
  const plan = JSON.parse(fs.readFileSync(planFile, 'utf8'));
  const windows = process.platform === 'win32';
  const files = new Map(Object.entries(plan.files).map(([file, entry]) => [normalize(file, windows), { file, ...entry }]));
  const baselines = plan.baselines;                     // [{file, text, functions}]
  const copies = plan.copy_files;                       // [file]
  const own = new Set([RUNTIME, GLOBAL_SETUP].map((file) => normalize(file, windows)));
  let viteRoot = root;
  const lookup = (id) => {
    const key = normalize(id, windows);
    if (files.has(key)) return files.get(key);
    // vite 6 hands an absolute file inside its root on as `/src/x.ts`
    return key.startsWith('/') ? files.get(normalize(path.join(viteRoot, key), windows)) : undefined;
  };
  const digest = (value) => createHash('sha1').update(JSON.stringify(value)).digest('hex');
  return {
    name: 'flowguard',
    enforce: 'pre',
    config() {
      process.env.FLOWGUARD_VITEST_PLAN = planFile;
      process.env.FLOWGUARD_VITEST_PYTHON = JSON.stringify(python);
      process.env.FLOWGUARD_VITEST_ROOT = root;
      return { test: { globalSetup: [GLOBAL_SETUP] } };
    },
    configResolved(config) {
      viteRoot = config.root;
      // the package whose tests run: a planned point in another package is not "not reached" by them
      process.env.FLOWGUARD_VITEST_PACKAGE = config.root;
    },
    // vitest 5 caches transforms on disk keyed by the source text: the plan belongs to that key
    configureVitest(context) {
      context.defineCacheKeyGenerator?.(({ id }) => {
        const entry = lookup(id);
        return entry ? digest([entry, plan.key]) : id.includes(BASELINE) ? digest(plan.key) : '';
      });
      // vitest 3.2 and later; an older vitest reports the red after the summary and in the exit status only
      return context.injectTestProjects?.({
        test: { name: 'flowguard', root: HERE, include: [SESSION], globals: true, environment: 'node',
          sequence: { groupOrder: LAST } },
      });
    },
    async resolveId(id, importer) {
      if (id === PREFIX + 'runtime') return RUNTIME;
      if (id.startsWith(PREFIX + 'baseline/')) return baselines[Number(id.slice(PREFIX.length + 9))].file + BASELINE;
      if (id.startsWith(PREFIX + 'copy/')) return copies[Number(id.slice(PREFIX.length + 5))];
      if (id === 'vitest' && importer && own.has(normalize(importer, windows))) {
        // the adapter ships with Python, outside node_modules: it uses the project's own vitest
        return this.resolve('vitest', path.join(viteRoot, 'package.json'), { skipSelf: true });
      }
      return null;
    },
    load(id) {
      if (!id.endsWith(BASELINE)) return null;
      const key = normalize(id.slice(0, -BASELINE.length), windows);
      const found = baselines.find((item) => normalize(item.file, windows) === key);
      if (!found) throw new Error(`flowguard: no baseline source for ${id}`);
      return found.text + '\n' + found.functions.map((fn) => `export { ${fn} as __flowguard_${fn} };`).join('\n') + '\n';
    },
    transform(code, id) {
      if (id.includes('?') || id.includes('\0')) return null;
      const entry = lookup(id);
      if (!entry) return null;
      const lines = code.split('\n');
      const tail = [`import * as __fg_rt from ${JSON.stringify(PREFIX + 'runtime')};`];
      if (entry.baseline !== null) tail.push(`import * as __fg_old from ${JSON.stringify(PREFIX + 'baseline/' + entry.baseline)};`);
      const aliases = new Map();
      for (const point of entry.points) {
        if (point.form === 'const') {
          const index = point.line - 1;
          if (!/\bconst\s/.test(lines[index] ?? '')) {
            throw new Error(`flowguard: ${point.rel}:${point.line} is not the const declaration of ${point.fn}`);
          }
          lines[index] = lines[index].replace(/\bconst\s/, 'let ');
        }
        const peers = point.copies.map((copy) => {
          if (!aliases.has(copy.index)) {
            aliases.set(copy.index, `__fg_c${aliases.size}`);
            tail.push(`import * as ${aliases.get(copy.index)} from ${JSON.stringify(PREFIX + 'copy/' + copy.index)};`);
          }
          const name = JSON.stringify('__flowguard_' + copy.fn);
          return `{ id: ${JSON.stringify(copy.id)}, params: ${JSON.stringify(copy.params)}, get fn() { return ${aliases.get(copy.index)}[${name}]; } }`;
        });
        const alias = JSON.stringify('__flowguard_' + point.fn);
        const old = entry.baseline === null ? '() => undefined' : `() => (${alias} in __fg_old ? __fg_old[${alias}] : null)`;
        const meta = { id: point.id, rel: point.rel, fn: point.fn, line: point.line, params: point.params,
          numbers: point.numbers, strings: point.strings, skip: point.skip };
        tail.push(`${point.fn} = __fg_rt.wrap(${JSON.stringify(meta)}, ${point.fn}, ${old}, () => [${peers.join(', ')}], ${plan.limit});`);
        tail.push(`export { ${point.fn} as __flowguard_${point.fn} };`);   // copies and baselines reach unexported functions too
      }
      return { code: lines.join('\n') + '\n' + tail.join('\n') + '\n', map: null };
    },
  };
}

// FlowGuard vitest adapter (minimal: vitest, ESM only). Python (`python -m flowguard.intent.vitest prepare`)
// writes a plan of real calls to record. This plugin only adds a recorder after each planned function;
// a const function becomes let so the recorder can remove itself. No old or copy module is imported.
// It also adds FlowGuard's own test project (session.test.mjs), run after the project's tests
// (sequence.groupOrder): its one test case fails on a red, so the red is in vitest's results (JSON, junit) too.
// It applies only to the vite servers vitest itself starts for a run (R85): what `vite build` and the dev server
// serve is never changed, nor a build or server that a test or a global setup starts inside a vitest run.
import fs from 'node:fs';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const RUNTIME = path.join(HERE, 'runtime.mjs');
const GLOBAL_SETUP = path.join(HERE, 'global-setup.mjs');
const SESSION = 'session.test.mjs';
const LAST = 1000;               // the session project's group comes after the others (vitest spreads its groups: keep it small)

// One spelling of a file for plan lookups: forward slashes, no query, a lower-case drive letter on Windows.
export function normalize(file, windows = process.platform === 'win32') {
  let text = String(file).split('?')[0].replace(/\\/g, '/');
  if (text.startsWith('/@fs/')) text = text.slice(4);
  if (windows && /^\/[A-Za-z]:\//.test(text)) text = text.slice(1);
  if (windows && /^[A-Za-z]:\//.test(text)) text = text[0].toLowerCase() + text.slice(1);
  return windows ? text.toLowerCase() : text;
}

// Whether a vite config being resolved is one of vitest's own servers (the root's or a project's): vitest passes its
// plugin (`vitest`, `vitest:project`) among the inline plugins of exactly those. A build, a dev server, and a server
// or build a test or a global setup starts read the same config file without it, also with VITEST in their
// environment (a worker's child process inherits it).
export function vitestServer(config) {
  const pending = [...(config.plugins ?? [])];
  while (pending.length) {
    const item = pending.pop();
    if (Array.isArray(item)) pending.push(...item);
    else if (item && typeof item === 'object' && (item.name === 'vitest' || item.name === 'vitest:project')) return true;
  }
  return false;
}

function sourceMap(code, file) {
  const alphabet = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
  const vlq = (number) => {
    let value = Math.abs(number) * 2 + (number < 0 ? 1 : 0), out = '';
    do { const part = value & 31; value = Math.floor(value / 32); out += alphabet[part + (value ? 32 : 0)]; } while (value);
    return out;
  };
  let previous = 0;
  // lines as JavaScript counts them (CR LF, LF, CR, U+2028, U+2029): stack positions are read in those lines
  const mappings = code.split(/\r\n|[\n\r\u2028\u2029]/).map((line, index) => {
    const first = 'AA' + (index ? 'C' : 'A') + vlq(-previous);
    previous = line.length;
    return first + ',CAAC'.repeat(line.length);
  }).join(';');
  return { version: 3, sources: [file], sourcesContent: [code], names: [], mappings };
}

export function flowguardPlugin({ plan: planFile, python, root, prepareSeconds }) {
  const plan = JSON.parse(fs.readFileSync(planFile, 'utf8'));
  const preparation = prepareSeconds ?? plan.prepare_seconds;
  if (typeof preparation !== 'number' || !Number.isFinite(preparation) || preparation < 0) {
    throw new Error('flowguard: this plan has no current preparation timing; run prepare again');
  }
  const windows = process.platform === 'win32';
  const files = new Map(Object.entries(plan.files).map(([file, entry]) => [normalize(file, windows), { file, ...entry }]));
  const own = new Set([RUNTIME, GLOBAL_SETUP].map((file) => normalize(file, windows)));
  let viteRoot = root, injected = false;
  const available = typeof process.getBuiltinModule === 'function';
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
    // vitest sets VITEST before it reads the config; only its own servers serve the test modules (`vitestServer`): a
    // build or dev server never applies this plugin, also through a flowguard.vitest.mjs written by an older init
    apply: (config, env) => Boolean(process.env.VITEST) && env.command === 'serve' && vitestServer(config),
    config() {
      process.env.FLOWGUARD_VITEST_PLAN = planFile;
      process.env.FLOWGUARD_VITEST_PYTHON = JSON.stringify(python);
      process.env.FLOWGUARD_VITEST_ROOT = root;
      process.env.FLOWGUARD_VITEST_PREPARE_SECONDS = String(preparation);
      return { test: { globalSetup: [GLOBAL_SETUP] } };
    },
    configResolved(config) {
      viteRoot = config.root;
      if (available) {
        const test = config.test ??= {};
        const setup = test.setupFiles == null ? [] : Array.isArray(test.setupFiles) ? test.setupFiles : [test.setupFiles];
        test.setupFiles = [RUNTIME, ...setup.filter((file) => normalize(file, windows) !== normalize(RUNTIME, windows))];
      }
      // the package whose tests run: a planned point in another package is not "not reached" by them
      process.env.FLOWGUARD_VITEST_PACKAGE = config.root;
    },
    // Vitest 4.1 caches transforms on disk: the plan and runtime location belong to that key
    configureVitest(context) {
      context.experimental_defineCacheKeyGenerator?.(({ id }) => {
        const entry = lookup(id);
        return entry ? digest([entry, plan.key, RUNTIME, available]) : '';
      });
      if (injected || !available) return;
      injected = true;
      return context.injectTestProjects?.({
        test: { name: 'flowguard', root: HERE, include: [SESSION], globals: true, environment: 'node', setupFiles: [], globalSetup: [],
          sequence: { groupOrder: LAST } },
      });
    },
    async resolveId(id, importer) {
      if (normalize(id, windows) === normalize(RUNTIME, windows)) return RUNTIME;
      if (id === 'vitest' && importer && own.has(normalize(importer, windows))) {
        // the adapter ships with Python, outside node_modules: it uses the project's own vitest
        return this.resolve('vitest', path.join(viteRoot, 'package.json'), { skipSelf: true });
      }
      return null;
    },
    load(id) {
      if (normalize(id, windows) === normalize(RUNTIME, windows)) return fs.readFileSync(RUNTIME, 'utf8');
      return null;
    },
    transform(code, id) {
      if (!available || id.includes('?') || id.includes('\0')) return null;
      const entry = lookup(id);
      if (!entry || !entry.points.some((point) => point.recordable !== false)) return null;
      const lines = code.split('\n');
      const tail = ['const __fg_rt = globalThis.__flowguard_vitest_runtime__;'];
      for (const point of entry.points) {
        if (point.recordable === false) continue;
        if (point.form === 'const') {
          const index = point.line - 1;
          if (!/\bconst\s/.test(lines[index] ?? '')) {
            throw new Error(`flowguard: ${point.rel}:${point.line} is not the const declaration of ${point.fn}`);
          }
          lines[index] = lines[index].replace(/\bconst(\s)/, 'let  $1');
        }
        const meta = { id: point.id, rel: point.rel, fn: point.fn, line: point.line };
        tail.push(`${point.fn} = __fg_rt.wrap(${JSON.stringify(meta)}, ${point.fn}, (original) => { ${point.fn} = original; });`);
      }
      return { code: lines.join('\n') + '\n' + tail.join('\n') + '\n', map: sourceMap(code, id) };
    },
  };
}

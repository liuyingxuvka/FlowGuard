// One worker bootstrap, loaded before user setup files. Real calls are never replayed here.
import { afterAll, expect } from 'vitest';

const proc = globalThis.process;
const builtin = typeof proc.getBuiltinModule === 'function' ? proc.getBuiltinModule.bind(proc) : null;
const writeData = builtin?.('fs').writeFileSync;
const join = builtin?.('path').join;
const thread = builtin?.('worker_threads').threadId;
const clock = builtin?.('perf_hooks').performance;
const now = clock?.now.bind(clock);
const stringify = JSON.stringify.bind(JSON), parse = JSON.parse.bind(JSON);
const finite = Number.isFinite;
const apply = Reflect.apply, read = Reflect.get, own = Object.hasOwn;
const source = Function.prototype.toString;
const Wrapper = Proxy;
const testState = expect.getState;
const dir = proc.env.FLOWGUARD_VITEST_OBS, pid = proc.pid;
const KEY = '__flowguard_vitest_runtime__';
const S = globalThis[KEY] ?? (globalThis[KEY] = { seen: new Map(), out: null, seconds: 0 });
S.originals ??= new WeakMap();      // each recorder's function, whose source its toString gives
const primitive = (value) => value === null || typeof value === 'boolean' || typeof value === 'string'
  || (typeof value === 'number' && finite(value) && !(value === 0 && 1 / value === -Infinity));

function write(record) {
  if (!dir) throw new Error('flowguard: FLOWGUARD_VITEST_OBS is not set; globalSetup did not run');
  // globalSetup owns this directory; the worker must neither create it nor use a project's fs mock.
  S.out ??= join(dir, `obs-${pid}-${thread}.jsonl`);
  // Node's native UTF-8 path writes directly; appendFileSync delegates through mutable fs exports.
  writeData(S.out, stringify(record) + '\n', { encoding: 'utf8', flag: 'a' });
}

if (builtin) afterAll(() => {
  write({ record_seconds: S.seconds });
  S.seconds = 0;
});

// R85: the project's tests see the function they would see without FlowGuard. The recorder is a Proxy of it whose
// only own behaviour is a call: every property (also one set with `Object.assign(f, ...)` or `f.x = ...` before or
// after wrapping), its prototype, `new` and `instanceof` are the function's own, and `f.toString()`, `String(f)` and
// `${f}` give its source (only Function.prototype.toString.call(f) says [native code], as for any Proxy).
export function wrap(point, fn, release) {
  if (!builtin) return fn;
  if (typeof fn !== 'function') throw new Error(`flowguard: ${point.rel}:${point.line} ${point.fn} is not a function`);
  const seen = S.seen.get(point.id) ?? new Set();
  S.seen.set(point.id, seen);
  let stopped = seen.size >= 20, unsupported = false;
  const called = (target, self, args) => {
    if (stopped || seen.size >= 20) return apply(fn, self, args);
    const start = now();
    let supported = true;
    for (const arg of args) if (!primitive(arg)) { supported = false; break; }
    const key = supported ? stringify(args) : null;
    const inputSeconds = (now() - start) / 1000;
    let result, threw = false, error;
    try { result = apply(fn, self, args); }
    catch (caught) { threw = true; error = caught; }
    const finish = now();
    if (!supported || threw || !primitive(result)) {
      if (!unsupported) {
        write({ id: point.id, reason: threw ? 'the real call raised; no exception object is inspected'
          : 'only primitive JSON arguments and results are recorded' });
        unsupported = true;
      }
    } else if (!seen.has(key)) {
      seen.add(key);
      write({ id: point.id, test: testState().currentTestName ?? '', args: parse(key), result });
      if (seen.size === 20) { stopped = true; release(fn); }
    }
    S.seconds += inputSeconds + (now() - finish) / 1000;
    if (threw) throw error;
    return result;
  };
  const wrapped = new Wrapper(fn, {
    apply: called,
    get(target, key, receiver) {
      const found = read(target, key, receiver);
      return key === 'toString' && found === source && !own(target, key) ? shown : found;
    },
  });
  S.originals.set(wrapped, fn);
  return wrapped;
}
const shown = { toString() { return apply(source, S.originals.get(this) ?? this, []); } }.toString;
S.wrap = wrap;

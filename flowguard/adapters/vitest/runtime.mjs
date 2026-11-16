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
const isProxy = builtin?.('util').types.isProxy;
const prototypeOf = Object.getPrototypeOf, descriptorsOf = Object.getOwnPropertyDescriptors;
const descriptorOf = Object.getOwnPropertyDescriptor, ownKeys = Reflect.ownKeys, isArray = Array.isArray;
const ObjectPrototype = Object.prototype, ArrayPrototype = Array.prototype;
// JSON data FlowGuard may record: primitives, and arrays and plain objects of them (at most 200 values, 6 levels).
// It is read through property descriptors only, so no project code runs: a proxy, a getter, a class instance, a
// toJSON (also one a project set on Object or Array's prototype), a symbol key, a hole, undefined or -0 is no data.
// A key that starts with $ is none either: FlowGuard's own encodings (`vitest.value`) use that prefix.
function data(value, budget = { left: 200 }, depth = 0) {
  if (primitive(value)) return true;
  if (value === null || typeof value !== 'object' || depth > 6 || --budget.left < 0 || isProxy(value)) return false;
  const array = isArray(value), prototype = prototypeOf(value);
  if (array ? prototype !== ArrayPrototype : prototype !== ObjectPrototype && prototype !== null) return false;
  if (descriptorOf(ObjectPrototype, 'toJSON') || (array && descriptorOf(ArrayPrototype, 'toJSON'))) return false;
  const own = descriptorsOf(value);
  for (const key of ownKeys(own)) {
    if (typeof key === 'symbol') return false;
    if (array && key === 'length') continue;
    const field = own[key];
    if (key.startsWith('$') || !('value' in field) || !field.enumerable) return false;
    if (!data(field.value, budget, depth + 1)) return false;
  }
  if (array) for (let index = 0; index < value.length; index++) if (!own[index]) return false;
  return true;
}

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
    for (const arg of args) if (!data(arg)) { supported = false; break; }
    const key = supported ? stringify(args) : null;
    const inputSeconds = (now() - start) / 1000;
    let result, threw = false, error;
    try { result = apply(fn, self, args); }
    catch (caught) { threw = true; error = caught; }
    const finish = now();
    if (!supported || threw || !data(result)) {
      if (!unsupported) {
        write({ id: point.id, reason: threw ? 'the real call raised; no exception object is inspected'
          : 'only JSON data arguments and results are recorded' });
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

// FlowGuard vitest adapter: the runtime a wrapped function calls. It records each real call (arguments and
// result as plain data; anything else is "unseen"), replays the call once over the representative values the
// Python plan gives, and runs the baseline function and the same-name copies on the same inputs. It decides
// nothing: classes, changes, copies and rules are judged in Python (flowguard.intent.vitest).
// While a replay runs, fs writes, fs.promises writes, child_process, net, http, https, fetch, dgram and worker
// threads are refused before they happen; a refusal voids the whole replay. A connection opened before the
// replay cannot be stopped this way, so a call whose arguments hold a database client is never replayed.
// The wrapped module, and so this runtime, loads inside the test's module graph, where a test may mock a Node
// module (`vi.mock('node:fs/promises', () => ({ writeFile: vi.fn() }))`): an ESM import of it here would receive
// the test's mock, and a mock without a default export fails the whole test file. Node's own require gives the
// real modules, which the guard patches and `syncBuiltinESMExports` passes on to their ESM exports.
import { createRequire, syncBuiltinESMExports } from 'node:module';
import { expect } from 'vitest';

const require = createRequire(import.meta.url);
const fs = require('node:fs');
const fsp = require('node:fs/promises');
const cp = require('node:child_process');
const net = require('node:net');
const http = require('node:http');
const https = require('node:https');
const dgram = require('node:dgram');
const wt = require('node:worker_threads');
const path = require('node:path');

const KEY = Symbol.for('flowguard.vitest.runtime');
const S = globalThis[KEY] ?? (globalThis[KEY] = {
  replaying: false, voided: '', patched: false, seen: new Set(), out: null,
  append: fs.appendFileSync, mkdir: fs.mkdirSync,
});

class Refused extends Error {}

// ---- the replay guard: installed once per worker, active only while S.replaying -------------------
function refusing(what, original) {
  return function (...args) {
    if (!S.replaying) return original.apply(this, args);
    if (!S.voided) S.voided = what;
    throw new Refused('flowguard: a replay may not use ' + what);
  };
}

const FS_WRITES = ['writeFile', 'writeFileSync', 'appendFile', 'appendFileSync', 'mkdir', 'mkdirSync', 'rm', 'rmSync',
  'rmdir', 'rmdirSync', 'unlink', 'unlinkSync', 'rename', 'renameSync', 'copyFile', 'copyFileSync', 'cp', 'cpSync',
  'truncate', 'truncateSync', 'symlink', 'symlinkSync', 'link', 'linkSync', 'chmod', 'chmodSync', 'chown', 'chownSync',
  'utimes', 'utimesSync', 'createWriteStream', 'mkdtemp', 'mkdtempSync'];
const FSP_WRITES = ['writeFile', 'appendFile', 'mkdir', 'rm', 'rmdir', 'unlink', 'rename', 'copyFile', 'cp', 'truncate',
  'symlink', 'link', 'chmod', 'chown', 'utimes', 'mkdtemp'];

function patch(object, names, what) {
  for (const name of names) {
    if (typeof object[name] === 'function') object[name] = refusing(what + '.' + name, object[name]);
  }
}

function install() {
  if (S.patched) return;
  S.patched = true;
  patch(fs, FS_WRITES, 'fs');
  patch(fsp, FSP_WRITES, 'fs.promises');
  for (const name of ['open', 'openSync']) {          // opening for writing is a write; reading stays allowed
    const original = fs[name];
    fs[name] = function (file, flags, ...rest) {
      if (S.replaying && typeof flags === 'string' && /[wa+]/.test(flags)) {
        if (!S.voided) S.voided = `fs.${name}(…, '${flags}')`;
        throw new Refused('flowguard: a replay may not open a file for writing');
      }
      return original.call(this, file, flags, ...rest);
    };
  }
  patch(cp, ['spawn', 'spawnSync', 'exec', 'execSync', 'execFile', 'execFileSync', 'fork'], 'child_process');
  patch(net, ['connect', 'createConnection', 'createServer'], 'net');
  patch(net.Socket.prototype, ['connect'], 'net.Socket');
  patch(http, ['request', 'get', 'createServer'], 'http');
  patch(https, ['request', 'get', 'createServer'], 'https');
  patch(dgram, ['createSocket'], 'dgram');
  if (typeof globalThis.fetch === 'function') globalThis.fetch = refusing('fetch', globalThis.fetch);
  const OriginalWorker = wt.Worker;
  wt.Worker = function (...args) {
    if (S.replaying) {
      if (!S.voided) S.voided = 'worker_threads.Worker';
      throw new Refused('flowguard: a replay may not start a thread');
    }
    return new OriginalWorker(...args);
  };
  syncBuiltinESMExports();
}

// ---- plain data only; everything else is "unseen" -------------------------------------------------
const UNSEEN = '$unseen';

function plain(value) {
  const proto = Object.getPrototypeOf(value);
  return proto === Object.prototype || proto === null;
}

export function encode(value, depth = 0) {
  if (depth > 12) return { [UNSEEN]: 'nesting' };
  if (value === null) return null;
  const t = typeof value;
  if (t === 'boolean' || t === 'string') return value;
  if (t === 'number') return Number.isFinite(value) ? (Object.is(value, -0) ? { $num: '-0' } : value) : { $num: String(value) };
  if (t === 'undefined') return { $undef: 1 };
  if (t === 'bigint') return { $big: String(value) };
  if (t !== 'object') return { [UNSEEN]: t };
  if (value instanceof Date) return { $date: Number.isNaN(value.getTime()) ? 'Invalid' : value.toISOString() };
  if (Array.isArray(value)) return value.map((item) => encode(item, depth + 1));
  if (value instanceof Set) return { $set: [...value].map((item) => encode(item, depth + 1)) };
  if (value instanceof Map) return { $map: [...value].map(([k, v]) => [encode(k, depth + 1), encode(v, depth + 1)]) };
  if (!plain(value)) return { [UNSEEN]: value.constructor?.name ?? 'object' };
  const out = {};
  for (const key of Object.keys(value)) out[key.startsWith('$') ? '$' + key : key] = encode(value[key], depth + 1);
  return out;
}

export function decode(value) {
  if (value === null || typeof value !== 'object') return value;
  if (Array.isArray(value)) return value.map(decode);
  if ('$num' in value) return Number(value.$num);
  if ('$undef' in value) return undefined;
  if ('$date' in value) return new Date(value.$date === 'Invalid' ? NaN : value.$date);
  if ('$big' in value) return BigInt(value.$big);
  if ('$set' in value) return new Set(value.$set.map(decode));
  if ('$map' in value) return new Map(value.$map.map(([k, v]) => [decode(k), decode(v)]));
  const out = {};
  for (const [key, item] of Object.entries(value)) out[key.startsWith('$$') ? key.slice(1) : key] = decode(item);
  return out;
}

function unseenIn(encoded) {
  if (encoded === null || typeof encoded !== 'object') return '';
  if (UNSEEN in encoded) return encoded[UNSEEN];
  for (const item of Array.isArray(encoded) ? encoded : Object.values(encoded)) {
    const found = unseenIn(item);
    if (found) return found;
  }
  return '';
}

function write(record) {
  if (!S.out) {
    const dir = process.env.FLOWGUARD_VITEST_OBS;
    if (!dir) throw new Error('flowguard: FLOWGUARD_VITEST_OBS is not set; the adapter\'s globalSetup did not run');
    S.mkdir(dir, { recursive: true });
    S.out = path.join(dir, `obs-${process.pid}-${wt.threadId}.jsonl`);
  }
  S.append(S.out, JSON.stringify(record) + '\n');
}

// ---- replay --------------------------------------------------------------------------------------
const DATABASE = /prisma|pool|client|connection|knex|sequelize|mongoose|redis|database|^db$|datasource|entitymanager/i;

function database(value, depth = 0) {
  if (value === null || typeof value !== 'object' || depth > 2) return '';
  for (const method of ['$transaction', '$queryRaw', '$connect']) if (typeof value[method] === 'function') return 'Prisma';
  if (typeof value.query === 'function' && ['connect', 'release', 'end', 'close'].some((m) => typeof value[m] === 'function')) {
    return value.constructor?.name ?? 'query/connect';
  }
  const name = value.constructor?.name ?? '';
  if (!plain(value) && DATABASE.test(name)) return name;
  for (const item of Object.values(value)) {
    const found = database(item, depth + 1);
    if (found) return found;
  }
  return '';
}

function neighbours(value) {          // the representable neighbours cells.epsilon gives (int 1, float 0.01..)
  if (Number.isInteger(value)) return [value - 1, value + 1];
  const text = String(value);
  const digits = text.includes('.') && !text.includes('e') ? text.split('.')[1].length : 2;
  const step = 10 ** -Math.max(2, Math.min(digits, 9));
  return [value - step, value + step];
}

const DAY = 86400000;
function dateNeighbours(date) {
  const midnight = date.getHours() === 0 && date.getMinutes() === 0 && date.getSeconds() === 0 && date.getMilliseconds() === 0;
  const utcMidnight = date.getTime() % DAY === 0;
  const step = midnight || utcMidnight ? DAY : 1000;   // a date steps a day; a time of day steps a second
  return [new Date(date.getTime() - step), new Date(date.getTime() + step)];
}

function unique(values) {
  const seen = new Set();
  return values.filter((value) => {
    const key = JSON.stringify(encode(value));
    return seen.has(key) ? false : (seen.add(key), true);
  });
}

function axisOf(actual, point) {
  if (typeof actual === 'boolean') return [false, true];
  if (typeof actual === 'number') {
    return unique([actual, ...(Number.isFinite(actual) ? neighbours(actual) : []), ...point.numbers.map(decode)]);
  }
  if (typeof actual === 'string') return unique([actual, ...point.strings]);
  if (actual instanceof Date && !Number.isNaN(actual.getTime())) return unique([actual, ...dateNeighbours(actual)]);
  return null;                         // a context: passed on as the test supplied it, on a copy
}

function copyArgs(args) {
  return args.map((arg) => (arg === null || typeof arg !== 'object' ? arg : structuredClone(arg)));
}

function call(fn, args) {
  if (typeof fn !== 'function') return { $missing: 1 };
  try {
    const out = fn(...args);
    if (out && typeof out.then === 'function') {
      out.then(() => {}, () => {});    // the replayed promise's own outcome is not compared
      return { [UNSEEN]: 'Promise' };
    }
    return encode(out);
  } catch (error) {
    // A replayed call's own exception is its outcome; a refusal already voided the replay (S.voided).
    if (error instanceof Refused) return { $refused: 1 };
    return { $threw: { name: error?.name ?? typeof error, message: String(error?.message ?? error) } };
  }
}

function contextProblem(args) {
  for (const arg of args) {
    if (typeof arg === 'function') return '参数里有函数（回调），不回放';
    if (arg === null || typeof arg !== 'object') continue;
    const client = database(arg);
    if (client) return `看不清：参数里有数据库客户端（${client}），不回放`;
    const unseen = unseenIn(encode(arg));
    if (unseen) return `参数里有不能复制的对象（${unseen}），不回放`;
  }
  return '';
}

function replay(point, fn, args, oldFn, copies, limit) {
  if (point.skip) return { status: 'grey', reason: point.skip, rows: [] };
  const problem = contextProblem(args);
  if (problem) return { status: 'grey', reason: problem, rows: [] };
  const axes = [];
  point.params.forEach((name, index) => {
    if (index >= args.length) return;
    const values = axisOf(args[index], point);
    if (values) axes.push([index, values]);
  });
  if (!axes.length) return { status: 'grey', reason: '没有可变化的简单参数', rows: [] };
  let total = 1;
  for (const [, values] of axes) total *= values.length;
  if (total > limit) return { status: 'grey', reason: `代表值组合 ${total} 个，超过上限 ${limit}`, rows: [] };
  let points = [[]];
  for (const [index, values] of axes) points = points.flatMap((prefix) => values.map((value) => [...prefix, [index, value]]));
  const rows = [];
  let first, again;
  S.replaying = true;
  S.voided = '';
  try {
    first = call(fn, copyArgs(args));
    for (const inputs of points) {
      if (S.voided) break;
      const replaced = copyArgs(args);
      for (const [index, value] of inputs) replaced[index] = value instanceof Date ? new Date(value) : value;
      const row = { in: inputs.map(([index, value]) => [point.params[index], encode(value)]), now: call(fn, replaced) };
      if (oldFn !== undefined) row.old = oldFn === null ? { $missing: 1 } : call(oldFn, copyArgs(replaced));
      if (copies.length) {
        row.copies = {};
        const named = Object.fromEntries(point.params.map((name, index) => [name, replaced[index]]));
        for (const copy of copies) {
          row.copies[copy.id] = copy.params.every((name) => name in named)
            ? call(copy.fn, copyArgs(copy.params.map((name) => named[name]))) : { $unmatched: 1 };
        }
      }
      rows.push(row);
    }
    again = call(fn, copyArgs(args));
  } finally {
    S.replaying = false;
  }
  if (S.voided) return { status: 'grey', reason: `看不清：回放中碰到 ${S.voided}，回放作废`, rows: [] };
  const unseen = unseenIn(first) || rows.map((row) => unseenIn(row.now)).find(Boolean);
  if (unseen) return { status: 'grey', reason: `看不清：结果不是可以比较的数据（${unseen}）`, rows: [] };
  if (JSON.stringify(first) !== JSON.stringify(again)) {
    return { status: 'grey', reason: '原值复查结果变了：可能有副作用或输入不稳定', rows: [] };
  }
  return { status: 'ok', reason: '', rows };
}

function testName() {
  return expect.getState().currentTestName ?? '';
}

// ---- the wrapper the transform installs ----------------------------------------------------------
export function wrap(point, fn, getOld, getCopies, limit) {
  install();
  if (typeof fn !== 'function') throw new Error(`flowguard: ${point.rel}:${point.line} ${point.fn} is not a function`);
  const wrapped = function (...args) {
    if (S.replaying) return fn.apply(this, args);
    const encoded = args.map((arg) => encode(arg));
    const key = point.id + '\u0000' + JSON.stringify(encoded);
    let replayed = null;
    if (!S.seen.has(key)) {           // one replay per distinct argument list and worker
      S.seen.add(key);
      replayed = replay(point, fn, args, getOld(), getCopies(), limit);
    }
    let result, threw = null;
    try {
      result = fn.apply(this, args);
    } catch (error) {
      threw = error;
    }
    const outcome = threw ? { $threw: { name: threw?.name, message: String(threw?.message ?? threw) } }
      : result && typeof result.then === 'function' ? { [UNSEEN]: 'Promise' } : encode(result);
    write({ id: point.id, test: testName(), args: encoded, result: outcome, ...(replayed ? { replay: replayed } : {}) });
    if (threw) throw threw;
    return result;
  };
  Object.defineProperty(wrapped, 'name', { value: fn.name });
  Object.defineProperty(wrapped, 'length', { value: fn.length });
  return wrapped;
}

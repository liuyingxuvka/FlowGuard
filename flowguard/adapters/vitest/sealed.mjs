// Source-only comparison after the test session. No project module is imported.
import fs from 'node:fs';
import vm from 'node:vm';

const setup = `
  'use strict';
  (() => {
  const allowed = new Set(('globalThis undefined NaN Infinity Object Array Number String Boolean BigInt Symbol '
    + 'Math JSON Date RegExp Map Set WeakMap WeakSet parseInt parseFloat isNaN isFinite '
    + 'encodeURI decodeURI encodeURIComponent decodeURIComponent Error TypeError ReferenceError SyntaxError '
    + 'RangeError EvalError URIError AggregateError').split(' '));
  for (const name of Object.getOwnPropertyNames(globalThis)) if (!allowed.has(name)) delete globalThis[name];
  Math.random = () => { throw new ReferenceError('uses Math.random'); };
  globalThis.Date = (() => {
    const Native = globalThis.Date, values = new WeakMap();
    class Date {
      constructor(...args) {
        if (!args.length) throw new ReferenceError('uses Date without arguments');
        values.set(this, new Native(...args));
      }
      static now() { throw new ReferenceError('uses Date.now'); }
      static UTC(...args) { return Native.UTC(...args); }
      static parse(...args) { return Native.parse(...args); }
    }
    for (const name of Object.getOwnPropertyNames(Native.prototype)) {
      if (name !== 'constructor' && typeof Native.prototype[name] === 'function') {
        Date.prototype[name] = function (...args) { return Native.prototype[name].apply(values.get(this), args); };
      }
    }
    return Date;
  })();
  })();
`;

function run(job) {
  const context = vm.createContext(undefined, { codeGeneration: { strings: false, wasm: false }, microtaskMode: 'afterEvaluate' });
  const program = `
    JSON.stringify((() => {
      try {
        const result = ${job.fn}(...JSON.parse(${JSON.stringify(JSON.stringify(job.args))}));
        if (result === 0 && 1 / result === -Infinity) return {reason: 'negative zero is not compared'};
        if (!(result === null || typeof result === 'boolean' || typeof result === 'string'
              || (typeof result === 'number' && result === result && result !== Infinity && result !== -Infinity))) {
          return {reason: 'only primitive JSON results are compared'};
        }
        return {value: result};
      } catch (error) {
        return {error: {name: '' + (error?.name ?? 'Error'), message: '' + (error?.message ?? error)}};
      }
    })())`;
  // The copy's source is compiled here, outside the context: a syntax error is then the host's own SyntaxError (syntax
  // the reader left in, such as TypeScript it does not strip), whose message is read; an error of a run in the
  // context is the copy's object and is never inspected.
  let compiling = false;
  try {
    vm.runInContext(setup, context, { timeout: 100 });
    compiling = true;
    const copy = new vm.Script("'use strict';\n" + job.source, { filename: 'flowguard-sealed.js' });
    compiling = false;
    copy.runInContext(context, { timeout: 100 });
    return JSON.parse(vm.runInContext(program, context, { timeout: 100 }));
  }
  catch (error) {
    return {reason: compiling ? `the sealed source does not parse: ${error.message}` : 'sealed execution failed or timed out'};
  }
}

const jobs = JSON.parse(fs.readFileSync(0, 'utf8'));
process.stdout.write(JSON.stringify(jobs.map(run)));

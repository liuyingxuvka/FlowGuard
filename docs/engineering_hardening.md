# Engineering Hardening

FlowGuard ships thin adoption surfaces around the existing Python API. The goal
is to make proven checks easier to run without changing the mathematical core.


## Command Line And Python Entry Points

The command line is intentionally small. Day to day it is:

```powershell
python -m flowguard read
python -m flowguard change
python -m flowguard release
python -m flowguard template --list
python -m flowguard map <scan|discover|digest|deps|check|lint|impact|models|confirm>
```

`python -m flowguard map models` runs the executable models bound in
`.flowguard/map.json`; every call executes them (results are never cached). The supported helpers are Python APIs:

- `check_loops()` for stuck-loop and non-terminating component review;
- `replay_trace()` and `default_conformance_rules()` for conformance replay;

None of these should hide expected-vs-observed statuses, `needs_human_review`,
or known limitations.

The wheel carries the maintained `examples` packages that the models and tests
import. A consumer check must execute at least one real model or check; a
successful `--help` or package import is only an entry point smoke check and
does not prove that the runtime dependencies are installed.

## Templates

The package exposes public-safe scaffolds for common agent situations:

- `validator_template_files()`: a finite contract-boundary starter
  that checks bad inputs against the real function.

The helpers return content instead of writing files so callers can decide where
and how to create project files. The CLI can print or write the same templates
(`python -m flowguard template --list` shows every name):

```powershell
python -m flowguard template validator --write .
```

Without `--write` the files are printed; `--force` overwrites existing files.

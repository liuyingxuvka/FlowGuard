# FlowGuard's retained product contracts

These concrete contracts describe the existing product checks and the round-14 design. They are not additional owner quotations. Rules added with this document have the visible `green*` evidence boundary.

- Project-owned code is inside the project, outside any directory containing pyvenv.cfg, outside site-packages, and outside the running interpreter prefix even without a pyvenv marker. The native boundary accepts absolute frame filenames; relative names stay outside it. An ordinary directory merely named .venv is not itself evidence of an environment. This retains the R33 path correction and its native/structure controls.
- Owner-word and document quotes use the same whitespace-and-elision comparison. Fragment order and every remaining word matter; blank or ellipsis-only quotes do not match. This retains the original request tests and the round-14 document-source design.
- Row expressions contain literals rather than globals, arithmetic or helper calls. Import aliases and a helper body do not hide a nonliteral expression. This is the literal-expression check; the loader separately checks the declaration's top-level origin.
- A nonempty UTF-8 owner request is saved byte for byte once. Neither the public request API nor the shared immutable writer overwrites an existing record. This retains the request archive format and its original tests.
- The collection sentinel succeeds only with the plugin loaded and every declared item collected or validly reused. A missing plugin or missing item fails rather than skipping. This is the round-14 sentinel contract.

R41 supplies the purpose: the model records rules and can expose conflicts. R46 supplies the finite exhaustive check and reuse principle. The rules below cover known regressions and shared decisions, not every function in the package.

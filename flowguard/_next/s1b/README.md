# S1b development inputs

This unpassed slice stays under the excluded `flowguard/_next/` directory.
It adds model-first guidance, useful request quotations and one portable flow
worker lifecycle for Linux and Windows.

`candidate.patch` applies the slice to the v0.73.0 source in a separate gate
copy. `manifest.json` lists its destinations. The patch preserves the base
version metadata; the gate copy prepares the future v0.74.0 metadata separately.

The gate runs the complete workflow, including native Windows `tests/flow`,
then independent review and the declared paired AI evaluation. Only after those
pass are the code, skill text and project rules moved into their official paths
and released. Current installed packages and skill text keep their released
behavior while this slice is staged.

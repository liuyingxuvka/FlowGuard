# KWP orchestrator (write values read through enum members)

`kwp_platform/orchestrator.py.txt` is `kwp_platform/orchestrator.py` of the owner's KWP project (HEAD `64479aa`),
copied verbatim with `cp` from a working-tree copy (no git command in the KWP repository). Its imports
(`.artifacts`, `.pipeline`) are not copied: the test reads map facts only and never imports it.
`KwpApplication.status` is written 16 times, always through `RunStatus` members (some in `a if c else b`);
`tests/intent_engine/test_owner_copies.py` requires all 16 values to be read.

# Contract Composition

Phase 14 adds optional contracts around existing `FunctionBlock` objects. It
does not replace the core model:

```text
F: Input x State -> Set(Output x State)
```

A `FunctionContract` can declare:

- accepted input type;
- output type;
- reads;
- writes;
- forbidden writes;
- preconditions;
- postconditions;
- idempotency rule;
- traceability rule;
- failure modes.

`check_trace_contracts()` checks a `Trace` against contracts for the function
steps it contains. The checker can catch:

- output-input type mismatch;
- forbidden writes;
- undeclared writes;
- precondition failure;
- postcondition failure;
- ownership and traceability predicates expressed as postconditions.

Contracts are intentionally incremental. Existing models can keep using plain
`FunctionBlock` objects, then add contracts for the functions whose boundaries
matter most.

In the benchmark corpus, contract/refinement pressure cases now include
explicit contract evidence such as `contract_checked=true` and
`contract_findings=postcondition`. This means the violation is not only a
scenario-specific invariant; it is also visible as a block-boundary contract
failure.

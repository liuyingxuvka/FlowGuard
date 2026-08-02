# Model-Test Payload Protocol

Load this file for files, JSON/YAML, schemas, serialized results, archives,
receipts, generated artifacts, or other externally inspectable payloads.

## ArtifactPayloadContract

Bind the payload's path/identity, producer, schema/version, required and
forbidden members, ordering/canonicalization rules, consumer, terminal status,
and content fingerprint. A command exit code without the required payload is
not passing evidence.

## Required Cases

Cover valid payload, missing payload, empty payload, missing required member,
unknown member, wrong type, stale schema, path mismatch, fingerprint mismatch,
partial write, and producer/consumer identity mismatch when applicable.

If payload content carries covered obligation ids, compare the exact declared
set; summaries, counts, filenames, logs, and copied receipts cannot substitute
for the canonical content.

## Completion

Each payload obligation has one external owner contract and current positive
and negative evidence, or a typed scoped/blocked disposition. Hand large
Cartesian payload matrices to ContractExhaustionMesh and TestMesh.

# Evidence Record

## Elementary Results

`small-support.json` is the deterministic output of
`src/check_small_support.py`. It lists all 16 elementary cycle-type
exclusions, checks the equality boundary cases, and records the incidence
arguments used for `3^7 1^22` and the elementary internal-type cases for
`3^8 1^19`.

## Certified `3^6 1^25` Result

The `orbit-p3-c6/` directory contains:

- four generation metadata files;
- four compressed binary DRAT proofs;
- four original Kissat logs;
- four original `drat-trim` logs;
- the exhaustive branch-coverage record;
- the independent CNF audit; and
- the certificate manifest.

Generated CNFs are not committed. `make verify-c6-certificates` regenerates
all four formulas and requires exact metadata, size, and SHA-256 agreement.

## Certified `3^8 1^19` Result

The `orbit-p3-c8/` directory contains:

- metadata for eight canonical and four strengthened formulas;
- six canonical and four strengthened compact DRAT proof streams;
- original solver logs and source-proof run records;
- proof-compaction and independent verification records;
- the normalized branch-coverage record;
- independent canonical and strengthened formula audits;
- the exhaustive two-class `t=4` matrix reduction; and
- the ten-branch certificate manifest.

Each logical proof is stored either as one `.drat.xz` file or as ordered
`.drat.xz.part-*` files whose exact concatenation is hash-bound in its
compaction record.

Run records distinguish proofs whose exact CNF and source-proof hashes were
written into the original solver log from legacy proofs carrying an explicit
post-run attestation. The latter label is a limitation of log provenance, not
a substitute for proof checking. Every retained compact proof passed its
historical independent verification. Release-grade fresh replay of the
complete four-branch c6 and ten-branch c8 packages also passes. Durable replay
records, checker binaries, build logs, and branch logs are retained under
`evidence/replay-c6/` and `evidence/replay-c8/`.

The two direct `t=4` root formulas are retained as audited reduction inputs,
but the release certificate uses the four strengthened matrix branches.
`make verify-c8-certificates` regenerates all 12 formulas, reconstructs the
manifest, and rejects missing, substituted, or hash-mismatched artifacts.

## Central Claim

```text
No graph on 43 vertices with clique number and independence number at most 4
has an automorphism of any of the 14 project-original cycle types recorded in
`research/claim.json`.
```

The certified cycle types are `3^6 1^25` and `3^8 1^19`. The other 12
project-original types have elementary proofs.

## Nonclaims

The evidence does not determine `R(5,5)`, change the interval
`43 <= R(5,5) <= 46`, establish asymmetry, exclude graphs with trivial
automorphism group, or cover any unlisted automorphism type.

# Evidence Record

## Elementary Result

`small-support.json` is the deterministic output of
`src/check_small_support.py`. It lists all 16 elementary cycle-type
exclusions, checks the equality boundary cases, and records the incidence
contradiction for `3^7 1^22`.

## Certified `3^6 1^25` Result

The `orbit-p3-c6/` directory contains:

- four generation metadata files;
- four compressed binary DRAT proofs;
- four original Kissat logs;
- four original `drat-trim` logs;
- the exhaustive branch-coverage record;
- the independent CNF audit; and
- the certificate manifest.

Generated CNFs are not committed. `make verify-certificates` deletes the
formula build directory, regenerates all four files, and requires exact
metadata, size, and SHA-256 agreement.

## Central Claim

```text
No graph on 43 vertices with clique number and independence number at most 4
has an automorphism of any of the 13 project-original cycle types recorded in
`research/claim.json`.
```

## Nonclaims

The evidence does not determine `R(5,5)`, exclude asymmetric graphs, or
cover any unlisted automorphism type.

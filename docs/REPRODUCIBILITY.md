# Reproducibility And Certificate Guide

## Trust Layers

The result has six distinct verification layers:

1. elementary graph-theoretic proofs;
2. executable arithmetic checks for every elementary boundary;
3. semantic tests for the orbit-CNF encoder and exact degree counters;
4. exhaustive normalized branch-coverage checks;
5. deterministic formula regeneration with independent artifact audits; and
6. fresh DRAT replay with `drat-trim`.

The DRAT proofs establish UNSAT for the generated formulas. Transfer to the
graph-theoretic claims also depends on the documented reductions, the encoder,
and the branch-cover arguments.

## Requirements

- Python 3.9 or newer
- `python-sat` for the full cardinality tests
- GNU Make or a compatible `make`
- `drat-trim` for fresh proof replay
- `pdflatex` for the report

Install Python test dependencies:

```bash
python3 -m pip install -r requirements-dev.txt
```

## Fast Checks

```bash
make test
make verify-text
make verify-elementary
```

`verify-elementary` checks all 16 elementary exclusions, including the
`3^7 1^22` incidence contradiction and the elementary `t=0,1,7,8` cases for
`3^8 1^19`. It also confirms the `3^6 1^25` branch cover, the eight normalized
`3^8 1^19` root branches, and the two strengthened `t=4` matrix classes.

## Formula Regeneration

```bash
make build-cnfs
make verify-cnfs
```

`build-cnfs` is incremental. `verify-cnfs` deletes both generated formula
directories and rebuilds every CNF from source, so verification cannot reuse
cached formulas.

The `3^6 1^25` family is generated under `build/orbit-p3-c6/`. Its four
formulas each have 501 edge-orbit variables, 67,709 total variables, 356,721
Ramsey signatures, and 910,918 clauses.

The `3^8 1^19` family is generated under
`build/verification/orbit-p3-c8/` and
`build/verification/orbit-p3-c8-t4-split/`. It contains eight canonical root
formulas and four strengthened `t=4` formulas. The independent semantic
verifiers rebuild the clause streams without importing the production
encoder.

The formula audits check:

- deterministic metadata equality;
- exact file size and SHA-256;
- DIMACS header and clause count;
- maximum literal range;
- independently reconstructed edge-orbit variables;
- exact branch unit clauses;
- exact clause-stream equality against reference encoders; and
- complete agreement with the retained branch inventories.

## Certificate Manifests

```bash
make verify-certificates
```

The target reconstructs both certificate manifests. It decompresses every
retained proof, recomputes compressed and decompressed hashes, checks original
solver and checker records, validates every regenerated CNF, and binds the
proofs to their semantic, coverage, and reduction audits.

Each `3^8 1^19` run record labels its artifact binding. `solver-log` means
the original solver log contains the exact CNF hash, proof size, and proof
hash. `post-run-attestation` identifies a legacy log without those embedded
values; it does not claim contemporaneous hash binding. In both cases the
retained compact proof is hash-checked, independently verified, and freshly
replayed against the regenerated CNF.

The `3^8 1^19` manifest requires exactly six canonical branches and four
strengthened `t=4` branches. A partial replay or the older unsplit `t=4`
cross-check cannot produce a release-grade theorem record.

## Fresh Proof Replay

Build `drat-trim` from its upstream source at:

```text
2e3b2dc0ecf938addbd779d42877b6ed69d9a985
```

Run:

```bash
make verify-proofs DRAT_TRIM=/absolute/path/to/drat-trim
```

The Makefile obtains the source checkout from the executable's parent
directory and requires the pinned, clean Git commit. The `3^8 1^19` replay
compiles a fresh checker from that source and records the source, compiler,
build log, and platform-specific executable hashes. If the executable is
stored elsewhere, also set:

```bash
DRAT_TRIM_SOURCE=/absolute/path/to/source-checkout
```

The replay tools stream each binary proof to `drat-trim` in binary mode. A
branch passes only when the checker exits zero and prints `s VERIFIED`. The
`3^8 1^19` replay additionally requires the complete retained manifest and
sets `release_grade_replay` only after all ten unique branches pass. The
official `make verify-proofs` path first regenerates the formulas and audit
reports through its certificate-verification dependency.

Fresh logs are written under `build/proof-replay-c6/` and
`build/proof-replay-c8/`.

## Resource Profile

- Generated CNFs: about 500 MB across both certificate families
- GPU: not used
- Recommended memory: at least 8 GB
- Expected class: minutes to tens of minutes on a commodity workstation

The retained package uses compacted proofs rather than raw solver traces.
Exact compressed and decompressed sizes are recorded per branch in the two
certificate manifests. Core extraction may use a single backward-checking
pass or optional fixpoint optimization; either output is retained only after
an independent verification pass succeeds.
Compaction records label the original proof as `solver-output` and the
retained compact proof as `retained-core`, even when their basenames match.

The deterministic release-manifest validator rejects any tracked package file
larger than 100,000,000 bytes. CI runs that validator before accepting a
release snapshot. A larger logical XZ proof may be stored as ordered parts
below that limit. The certificate records every part hash plus the byte count
and SHA-256 digest of their exact concatenation before decompression.

## Evidence Map

| Artifact | Role |
| --- | --- |
| `evidence/small-support.json` | Elementary exclusion list |
| `evidence/orbit-p3-c6/` | Four-branch `3^6 1^25` certificate package |
| `evidence/orbit-p3-c8/branch-coverage.json` | Exhaustive normalized root reduction |
| `evidence/orbit-p3-c8/canonical-cnf-audit.json` | Canonical DIMACS audit |
| `evidence/orbit-p3-c8/canonical-formula-semantics-audit.json` | Independent canonical formula reconstruction |
| `evidence/orbit-p3-c8/t4-matrix-reduction.json` | Two-class `t=4` reduction |
| `evidence/orbit-p3-c8/t4-formula-semantics-audit.json` | Independent strengthened formula reconstruction |
| `evidence/orbit-p3-c8/certificate-manifest.json` | Ten-branch proof and provenance manifest |
| `evidence/orbit-p3-c8/*.drat.xz` and `*.drat.xz.part-*` | Retained compact binary DRAT proof streams |

## Failure Interpretation

- A solver timeout is not an exclusion.
- A solver UNSAT line without a checked proof is not a retained certificate.
- A proof checked against a hash-mismatched CNF is irrelevant.
- Passing unit tests alone does not establish either certified theorem.
- A partial `3^8 1^19` replay is explicitly non-release.
- A failed clean replay blocks release until explained and resolved.

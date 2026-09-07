# Reproducibility And Certificate Guide

## Trust Layers

The result has five distinct verification layers:

1. an elementary mathematical proof;
2. executable arithmetic checks for every elementary boundary;
3. semantic tests for the orbit-CNF and exact degree counter;
4. deterministic formula regeneration plus independent artifact auditing; and
5. fresh DRAT replay with `drat-trim`.

The DRAT proofs establish UNSAT for the generated formulas. Correct transfer
to the graph-theoretic claim also depends on the encoder and the four-branch
coverage argument.

## Requirements

- Python 3.9 or newer
- `python-sat` for the full cardinality test
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

`verify-elementary` checks the 16 elementary exclusions, including the
`3^7 1^22` incidence contradiction, and confirms that the stored
branch-coverage record accounts for all 64 certificate root patterns.

## Formula Regeneration

```bash
make build-cnfs
make verify-cnfs
```

`build-cnfs` is the optional incremental build target. `verify-cnfs` first
deletes the formula directory and then regenerates all four CNFs from source,
so a verification run cannot reuse cached formulas. The build produces files
under `build/orbit-p3-c6/`. Each formula has:

```text
edge-orbit variables: 501
total variables: 67,709
Ramsey signatures: 356,721
clauses: 910,918
```

`verify-cnfs` checks:

- deterministic metadata equality;
- exact file size and SHA-256;
- DIMACS header and clause count;
- maximum literal range;
- independent reconstruction of root edge-orbit variables;
- equality of the common formula body; and
- exact branch unit clauses.

## Certificate Manifest

```bash
make verify-certificates
```

This decompresses every retained proof, recomputes compressed and
decompressed hashes, checks original solver and checker logs, validates every
regenerated CNF, and reconstructs the certificate manifest. The
reconstructed record must match the retained manifest exactly. The tool
hashes in that manifest identify the historical binaries used for the
original run.

## Fresh Proof Replay

Build `drat-trim` from its upstream source. The replay target requires the
executable to remain inside a checkout at the following audited commit:

```text
2e3b2dc0ecf938addbd779d42877b6ed69d9a985
```

Run:

```bash
make verify-proofs DRAT_TRIM=/absolute/path/to/drat-trim
```

The Makefile obtains the source checkout from the executable's parent
directory and refuses to run unless its Git commit matches the pinned value.
If the executable is stored elsewhere, also set
`DRAT_TRIM_SOURCE=/absolute/path/to/source-checkout`.

The replay tool decompresses each binary proof in memory and supplies it to
`drat-trim` in binary mode. A branch passes only when the checker exits zero
and prints `s VERIFIED`. Fresh logs and a replay summary are written under
`build/proof-replay/`.

## Resource Profile

- Generated CNFs: about 134 MB total
- Retained compressed proofs: about 57 MB total
- Decompressed proofs: about 159 MB total
- GPU: not used
- Recommended memory: at least 4 GB
- Expected class: minutes on a commodity workstation

## Evidence Map

| Artifact | Role |
| --- | --- |
| `evidence/small-support.json` | Elementary exclusion list |
| `evidence/orbit-p3-c6/branch-coverage.json` | Exhaustive 64-pattern reduction |
| `evidence/orbit-p3-c6/cnf-audit.json` | Independent formula artifact audit |
| `evidence/orbit-p3-c6/certificate-manifest.json` | Central hashes and outcomes |
| `evidence/orbit-p3-c6/*.drat.xz` | Retained binary DRAT proofs |
| `evidence/orbit-p3-c6/*-proof.log` | Original solver records |
| `evidence/orbit-p3-c6/*-drat-trim.log` | Original checker records |

## Failure Interpretation

- A solver timeout is not an exclusion.
- A solver UNSAT line without a checked proof is not a retained certificate.
- A proof that verifies against a hash-mismatched CNF is irrelevant.
- Passing unit tests alone does not establish the 43-vertex theorem.
- A failed clean replay blocks release until explained and resolved.

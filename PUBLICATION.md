# Publication Dossier

## Release Identity

| Field | Value |
| --- | --- |
| Title | Prime-Order Automorphism Exclusions for Ramsey (5,5;43) Graphs |
| Author | Ruturaj R Raval |
| Affiliation | Independent Researcher |
| ORCID | `0000-0003-4930-8981` |
| Candidate version | `v0.1.0` |
| License | MIT |
| Package status | not yet released |

Package status: not yet released.

## Claim-Safe Public Summary

As of 2026-09-08, the package excludes 14 prime-order automorphism cycle
types that audited public case lists and coverage ledgers still marked
pending, uncovered, or unfinished. Twelve types follow from elementary
fixed-point, degree, and incidence arguments. The types `3^6 1^25` and
`3^8 1^19` follow from 14 retained UNSAT certificates checked by
`drat-trim`.

## Supported Result And Delta

The audited starting interval remains `43 <= R(5,5) <= 46`. The project does
not change that interval. Its original delta is structural:

```text
2^c 1^(43-2c), 1 <= c <= 3
3^c 1^(43-3c), 1 <= c <= 8
5^c 1^(43-5c), 1 <= c <= 3
```

These 14 cycle types were marked pending, uncovered, or unfinished in the
public artifacts audited through 2026-09-08. A targeted public search found
no earlier completed exclusion or independently checkable certificate. This
is a dated public-record resolution claim, not an absolute-priority or
first-attempt claim.

## Significance And Reuse

The result removes finite symmetry classes from future searches for a
43-vertex Ramsey graph. The elementary arguments can be reused for related
Ramsey automorphism problems, and the orbit-CNF plus proof-replay pipeline can
be extended to remaining cycle types.

## Verification And Evidence

- Elementary arithmetic checker: `src/check_small_support.py`
- Orbit-CNF generator: `src/orbit_cnf.py`
- Branch coverage audit: `evidence/orbit-p3-c6/branch-coverage.json`
- Independent formula audit: `evidence/orbit-p3-c6/cnf-audit.json`
- Certificate manifest: `evidence/orbit-p3-c6/certificate-manifest.json`
- Retained proofs: `evidence/orbit-p3-c6/*.drat.xz`
- Fresh replay tool: `tools/replay_proofs.py`
- Retained c6 replay: `evidence/replay-c6/fresh-proof-replay.json`
- `3^8 1^19` coverage: `evidence/orbit-p3-c8/branch-coverage.json`
- `3^8 1^19` certificate manifest:
  `evidence/orbit-p3-c8/certificate-manifest.json`
- `3^8 1^19` retained proof streams:
  `evidence/orbit-p3-c8/*.drat.xz` and `*.drat.xz.part-*`
- Combined c8 replay tool: `tools/replay_c8_proofs.py`
- Retained c8 replay: `evidence/replay-c8/fresh-proof-replay.json`
- Committed inspected report:
  `paper/ramsey-number-5-5-paper-v0.1.0.pdf`
- Retained inspected build log:
  `paper/ramsey-number-5-5-paper-v0.1.0.log`
- Report binding: `paper/release-pdf.json`
- Package manifest: `release-manifest.sha256`

## Claim Boundary And Limitations

This package does not determine `R(5,5)`, improve its global bounds, prove
asymmetry, exclude every nontrivial automorphism, or classify all
`R(5,5,43)` graphs. The proof certificates validate a finite encoded
statement and rely on the correctness of the encoder, proof checker, and
hardware. The encoder is extensively tested but not formally verified.

## Provenance And Licensing

Project-original code, proofs, evidence records, and documentation are MIT
licensed. The two retained `drat-trim` checker executables remain under the
upstream MIT license reproduced at `third_party/drat-trim/LICENSE`.
Referenced papers, Kissat, and external public coverage records retain their
own rights. No third-party source code or Ramsey graph catalog is
redistributed in this package.

## Review Status

The elementary proof and novelty scope received a separate adversarial
consistency review within the project. Formula structure, branch coverage,
artifact hashes, and DRAT proofs have independent executable checks. A
separate prerelease package reproducibility audit identified and corrected
release-gate enforcement, closed-world manifest checking, source-proof
provenance validation, multipart inventory checks, and candidate-versus-final
CI separation. Complete fresh local replays now verify all four c6 and all ten
c8 branches. The corrected committed snapshot passed separate read-only
mathematical and release-integrity reviews with no remaining findings. Hosted
replay, external journal review, and proof-assistant verification have not
occurred.

## Remaining Work And Release Gate

Before release:

1. Complete hosted candidate CI on the exact public candidate.
2. Bind the successful hosted run ID and SHA into the release gate.
3. Verify the tag-bound PDF, source, and checksum assets in hosted CI.
4. Publish only the exact assets uploaded by the successful tag workflow.
5. Confirm the public claim and dissemination text against the tagged package.

Both certificate manifests are generated and independently reconstructed by
the certificate-verification targets. The local release-grade replay records
verify all 14 retained proof branches and are retained with their checker
binaries and logs. The rebuilt nine-page report has been inspected page by
page, committed, and bound to its source and build log by SHA-256.

The next order-3 research target is `3^9 1^16`.

## Citation

The planned citation record is `CITATION.cff`. No DOI or tagged release is
claimed before archival.

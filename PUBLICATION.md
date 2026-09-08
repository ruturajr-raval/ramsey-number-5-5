# Publication Dossier

## Release Identity

| Field | Value |
| --- | --- |
| Title | Prime-Order Automorphism Exclusions for Ramsey (5,5;43) Graphs |
| Author | Ruturaj R Raval |
| Affiliation | Independent Researcher |
| ORCID | `0000-0003-4930-8981` |
| Release | `v0.1.0` |
| Release date | 2026-09-08 |
| Audited candidate commit | `27ea32178dfe9169f8d787d424013921050a1d3d` |
| Protected release commit | `efbd19f319e9131fd550ec149bd1e5b72a82efee` |
| GitHub release | [`v0.1.0`](https://github.com/ruturajr-raval/ramsey-number-5-5/releases/tag/v0.1.0) |
| Version DOI | `10.5281/zenodo.22653273` |
| Concept DOI | `10.5281/zenodo.22653272` |
| License | MIT |
| Package status | published and independently download-verified |

The protected release tag is a descendant of the audited candidate commit.
The descendant changes publication metadata, release validation, and the
paper availability statement; it does not change the mathematical formulas,
proof certificates, or supported theorem. GitHub release `385004910` was
published at `2026-09-08T19:25:14Z` and is marked immutable. Zenodo record
`22653273` was published at `2026-09-08T20:17:53Z`.

## Claim-Safe Public Summary

The package demonstrates 18 prime-order automorphism cycle-type exclusions.
Fourteen form the original dated public-record delta: twelve follow from
elementary fixed-point, degree, and incidence arguments, while `3^6 1^25`
and `3^8 1^19` follow from 14 retained UNSAT certificates checked by
`drat-trim`. The other four are elementary reproofs of cases already covered
computationally.

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
- Current branch package manifest: `release-manifest.sha256`

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
c8 branches. The corrected candidate passed separate read-only mathematical
and release-integrity reviews. The final publication metadata, paper
availability statement, and release validators then received another
exact-snapshot review. Exact-SHA hosted candidate replay passes. Protected
tag-bound recovery run `34267807536` passed, and a second
owner-authenticated ruleset audit confirmed no bypass actors before the
GitHub release was created. All public GitHub and Zenodo assets were
independently downloaded and matched the release SHA-256 values. External
journal review and proof-assistant verification have not occurred.

## Release Verification And Archive

Release `v0.1.0` passed the recorded publication sequence:

1. Exact-SHA hosted candidate CI passed on the audited candidate.
2. The successful hosted run ID and SHA are bound into the release gate.
3. The annotated tag was protected against update and deletion without
   bypass.
4. The protected-tag recovery workflow verified the PDF, source, checksum
   file, release commit, tag object, and ruleset.
5. A second owner-authenticated ruleset audit passed before release creation.
6. The immutable GitHub release and Zenodo record received the same three
   verified assets.
7. Independent public downloads from both services matched the recorded
   SHA-256 values.

Both certificate manifests are independently reconstructed by the
certificate-verification targets. The local and candidate-hosted
release-grade replay records verify all 14 retained proof branches. The
nine-page report was inspected page by page, committed, and bound to its
source and build log by SHA-256.

The manifest archived in the immutable `v0.1.0` source package has SHA-256
`76e60847abab01adb2646e50e000e850849f7b9f24d8f3622daac10853fea692`.
The root manifest on `main` is intentionally a separate current-branch
integrity record that includes the post-publication evidence.

The release gate deliberately freezes the `v0.1.0` paper path, DOI, tag, and
audited identity. A later version must explicitly update those versioned
constants, citation records, and release metadata before candidate or tag CI
can authorize it. The lifecycle guard prevents mutable `main` from rebuilding
an already published version under the same asset names.

The complete publication facts are recorded in
`research/publication-record.json`. The protected-tag workflow evidence is
retained in `research/tag-recovery-final-evidence.json`, and the second
owner-authenticated audit is retained in
`research/tag-release-publication-audit.json`. The original
`research/release-gate.json` remains the historical prerelease authorization
record.

The next order-3 research target is `3^9 1^16`.

## Citation

Ruturaj R Raval, "Prime-Order Automorphism Exclusions for Ramsey (5,5;43)
Graphs," version 0.1.0, 2026. DOI: `10.5281/zenodo.22653273`.

The machine-readable citation record is `CITATION.cff`.

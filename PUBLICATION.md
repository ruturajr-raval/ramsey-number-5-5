# Publication Dossier

## Release Identity

| Field | Value |
| --- | --- |
| Title | Prime-Order Automorphism Exclusions for Ramsey `(5,5,43)` Graphs |
| Author | Ruturaj R Raval |
| Affiliation | Independent Researcher |
| ORCID | `0000-0003-4930-8981` |
| Candidate version | `0.1.0` |
| License | MIT |
| Package status | not yet released |
| Version DOI | not yet assigned |
| Concept DOI | not yet assigned |

Package status: not yet released.

## Claim-Safe Summary

The package excludes 12 prime-order automorphism cycle types that dated
public coverage left unresolved. Eleven small-support types follow from an
elementary fixed-point theorem. The additional type `3^6 1^25` follows from
four retained UNSAT certificates checked by `drat-trim`.

## Supported Result And Delta

The audited starting interval remains `43 <= R(5,5) <= 46`. The project does
not change that interval. Its original delta is structural:

```text
2^c 1^(43-2c), 1 <= c <= 3
3^c 1^(43-3c), 1 <= c <= 6
5^c 1^(43-5c), 1 <= c <= 3
```

These 12 cycle types were listed as uncovered or unfinished in the public
artifacts audited through 2026-09-07.

## Significance And Reuse

The result removes finite symmetry classes from future searches for a
43-vertex Ramsey graph. The fixed-point argument can be reused for related
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
- Package manifest: `release-manifest.sha256`

## Claim Boundary And Limitations

This package does not determine `R(5,5)`, improve its global bounds, prove
asymmetry, exclude every nontrivial automorphism, or classify all
`R(5,5,43)` graphs. The proof certificates validate a finite encoded
statement and rely on the correctness of the encoder, proof checker, and
hardware. The encoder is extensively tested but not formally verified.

## Provenance And Licensing

Project-original code, proofs, evidence records, and documentation are MIT
licensed. Referenced papers, Kissat, `drat-trim`, and external public
coverage records retain their own rights. No third-party source code or
Ramsey graph catalog is redistributed in this package.

## Review Status

The elementary proof and novelty scope received a separate adversarial
consistency review within the project. Formula structure, branch coverage,
artifact hashes, and DRAT proofs have independent executable checks. A
separate package reproducibility audit completed with no remaining findings.
External journal review and proof-assistant verification have not occurred.

## Remaining Work And Release Gate

Before release:

1. Run the repository and release-manifest validators.
2. Refresh the prior-art search immediately before release.
3. Prepare the tagged release and archive assets.
4. Confirm the public claim and dissemination text against the tagged package.

## Citation

The planned citation record is `CITATION.cff`. No DOI or tagged release is
claimed before archival.

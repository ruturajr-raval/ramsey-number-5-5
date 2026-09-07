# Release Notes

## Unreleased

- Proves an elementary exclusion theorem for 16 prime-order automorphism
  cycle types of hypothetical Ramsey `(5,5,43)` graphs.
- Identifies 12 of those elementary cases as uncovered or unfinished in the
  audits.
- Adds four independently checked DRAT certificates excluding the additional
  cycle type `3^6 1^25`.
- Adds a counting proof excluding `3^7 1^22` without a solver certificate.
- Excludes `3^8 1^19` through elementary internal-type reductions, an exact
  structural slack identity, and ten independently replayed DRAT
  certificates.
- Classifies the `t=4` mixed-link matrices into two equivalence classes and
  verifies the resulting four strengthened branches.
- Retains exact formula, proof, log, and tool hashes in a machine-readable
  certificate manifest.
- Retains the two checker executables used by the release-grade replays with
  the upstream `drat-trim` MIT license.
- Does not determine `R(5,5)`, change `43 <= R(5,5) <= 46`, or exclude
  asymmetric graphs.
- The next order-3 research target is `3^9 1^16`; public release remains subject to
  the recorded prerelease gate.

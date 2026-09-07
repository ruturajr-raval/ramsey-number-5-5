# Research Plan

## Current Milestone

The 16-type elementary theorem, including `3^7 1^22`, and the certified
exclusions of `3^6 1^25` and `3^8 1^19` are complete. The package remains
prerelease under the recorded release gate.

## Ranked Next Targets

### 1. Additional order-3 types

Attempt `3^9 1^16` and then increase `c`, preferring elementary reductions
when available. The completed `3^8 1^19` proof establishes the following
contract for computational exclusions:

- complete branch coverage;
- deterministic CNF hashes;
- retained compressed proofs;
- independent `drat-trim` replay; and
- explicit comparison with current public coverage.

### 2. Remaining order-2 types

Develop stronger fixed-point or quotient constraints before launching large
SAT runs. Priority goes to arguments that eliminate multiple cycle types at
once rather than isolated certificates.

### 3. Remaining order-5 types

Combine the fixed-point lemma with quotient-graph structure and the public
partial certificate frontier. Avoid duplicating branches already closed by
current campaigns.

### 4. Full prime-order asymmetry theorem

The strongest finite intermediate objective is:

```text
Every hypothetical Ramsey (5,5,43) graph has no nontrivial prime-order
automorphism.
```

By Cauchy's theorem this would imply asymmetry. It remains far beyond the
current result because many order-2, order-3, and order-5 types are open.

### 5. Parent Ramsey problem

Only after substantial structural progress should the project attempt a
global construction or exclusion at order 43. An asymmetric graph is not
addressed by the current automorphism route.

## Acceptance Gates

A new cycle type is accepted only when:

1. the public novelty audit is refreshed;
2. the mathematical reduction and all assumptions are explicit;
3. an elementary proof has a deterministic arithmetic audit and focused
   regression tests, or every computational symmetry branch is enumerated
   and justified;
4. each computational CNF is deterministic and independently audited;
5. every computational UNSAT result has a retained proof that passes an
   independent checker; and
6. the exact nonclaim boundary is documented.

## Kill Criteria

Pause a computational branch when:

- no complete branch cover exists;
- proof size cannot be retained or archived responsibly;
- the same result already exists publicly;
- formula generation cannot be independently audited;
- solver output is only `UNKNOWN`; or
- resource growth offers no credible route to a checked conclusion.

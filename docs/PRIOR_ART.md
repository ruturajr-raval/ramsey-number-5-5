# Prior-Art And Novelty Audit

Audit date: 2026-09-07

## Global Ramsey Frontier

| Date | Result | Source role |
| --- | --- | --- |
| 1989 | `R(5,5) >= 43` | Exoo lower bound |
| 1995 | `R(4,5)=25` | Degree-interval ingredient |
| 1997 | `R(5,5) <= 49` | McKay and Radziszowski |
| 2018 | `R(5,5) <= 48` | Angeltveit and McKay |
| 2025 | `R(5,5) <= 46` | Angeltveit and McKay |
| 2026-09-07 | `43 <= R(5,5) <= 46` | Audited starting frontier |

The project does not change this interval.

## Closest Automorphism Work

The public prescribed-automorphism projects formulate the same broad finite
search space. Their contributions include certificates for larger prime
orders and all order-7 types.

The closest current public record is:

```text
repository: https://github.com/wustep/maths
path: problems/ramsey-r55
audited commit: 4b7b8275d41682a98add180ee05540be84037100
commit date: 2026-09-06
```

Its q7 case list contains four representatives for `3^6 1^25`, named
`p3_c6_k1`, `p3_c6_k2`, `p3_c6_k3`, and `p3_c6_k6`. It also partitions
`3^7 1^22` into four representatives with fixed-cycle parameters `[0,7]`,
`[1,6]`, `[2,5]`, and `[3,4]`. The expected CNF hashes are null, the four
`3^7 1^22` records are pending, and the campaign record states that the
remaining order-3 cycle types are unfinished.

The earlier coverage audit at
[`AlecKriebel/Math`](https://github.com/AlecKriebel/Math/tree/main/ramsey55)
lists both `3^6 1^25` and `3^7 1^22` among 54 uncovered prime-order types.
The audited main commit was
`137ffa9f1a340f621651395ad0236cf1bdadb51c`.

The repository
[`techno-optimist/r55-rigidity-certificates`](https://github.com/techno-optimist/r55-rigidity-certificates)
provides related larger-prime certificates. The audited main commit was
`1bfd71681c2a26dcbf91b74389cd963458dc9e78`.

## Exact Novelty Searches

Public code search was performed for:

```text
"3^6 1^25"
"3^{6}1^{25}"
p3_c6 ramsey
p3-c6 ramsey
"3^7 1^22"
"3^{7}1^{22}"
p3_c7 ramsey
p3-c7 ramsey
```

The exact cycle-type searches returned only case listings in the repositories
above. No public construction, completed exclusion, or independently
checkable certificate for either type was found.

Targeted searches also examined the fixed-point threshold `26`, the degree
expressions `3c+3`, `39-3c`, `2c+12`, and `30-2c`, and the complete
small-support list. No earlier statement of the elementary theorem was found.

Negative search evidence cannot establish absolute priority. The safe
novelty statement is:

> To the best of the targeted search of public literature and repositories
> available through 2026-09-07, no previous source states or proves the 12
> project-original elementary exclusions or supplies a completed certificate
> for `3^6 1^25`.

The `3^7 1^22` case had been explicitly prepared as a finite computational
case before this project. The novelty claim is therefore resolution, not
first attempt.

## Methodological Ancestry

Orbit-based Ramsey search, automorphism restrictions, SAT encodings, and DRAT
proofs are established methods and are not claimed as new. The original
contribution is the applied elementary theorem, its exact cycle-type
consequences including `3^7 1^22`, and the completed proof-logged exclusion
of `3^6 1^25`.

## Primary References

1. Geoffrey Exoo, "A lower bound for R(5,5)," Journal of Graph Theory 13(1),
   97-98, 1989.
2. Brendan D. McKay and Stanislaw P. Radziszowski, "R(4,5)=25," Journal of
   Graph Theory 19(3), 309-322, 1995.
3. Brendan D. McKay and Stanislaw P. Radziszowski, "Subgraph counting
   identities and Ramsey numbers," Journal of Combinatorial Theory, Series B
   69(2), 193-209, 1997.
4. Vigleik Angeltveit and Brendan D. McKay, "R(5,5) <= 48," Journal of Graph
   Theory 89(1), 5-13, 2018.
5. Vigleik Angeltveit and Brendan D. McKay, "R(5,5) <= 46,"
   [arXiv:2409.15709](https://arxiv.org/abs/2409.15709), version 2, 2025.
6. R. E. Greenwood and A. M. Gleason, "Combinatorial relations and
   chromatic graphs," Canadian Journal of Mathematics 7, 1-7, 1955.

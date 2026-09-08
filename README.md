# Prime-Order Automorphism Exclusions for Ramsey `(5,5;43)` Graphs

## Project Overview

| Field | Value |
| --- | --- |
| Author | Ruturaj R Raval |
| Affiliation | Independent Researcher |
| ORCID | [0000-0003-4930-8981](https://orcid.org/0000-0003-4930-8981) |
| Field | Ramsey theory, graph automorphisms, and proof-logged SAT |
| Problem | Restrict prime-order automorphisms of hypothetical Ramsey `(5,5,43)` graphs |
| Current result | As of 2026-09-08, fourteen automorphism cycle types marked pending, uncovered, or unfinished in audited public case lists and coverage ledgers are excluded: twelve by elementary arguments, `3^6 1^25` by four checked DRAT certificates, and `3^8 1^19` by ten checked DRAT certificates after elementary and structural reductions |
| Result type | Scoped structural theorem and certified finite exclusion |
| Release | not yet released |
| Version DOI | not yet assigned |
| Concept DOI | not yet assigned |
| License | MIT |

The repository develops elementary structural arguments and proof-logged SAT
exclusions for prime-order automorphisms of a hypothetical graph on 43
vertices with neither a clique nor an independent set of size 5.

All 14 retained proof packages exist. The complete c6 and c8 certificate
manifests, both local release-grade replays, and separate mathematical and
release-integrity reviews pass. Hosted CI, public release, and DOI remain
pending.

## Problem And Background

The diagonal Ramsey number `R(5,5)` is the least integer `n` such that every
graph on `n` vertices contains a clique of size 5 or an independent set of
size 5. Write `R(5,5,n)` for the class of finite simple undirected graphs on
`n` vertices with clique number and independence number at most 4.

The problem's origin is Ramsey's 1930 theorem on unavoidable homogeneous
sets. For this specific diagonal case, Exoo established the enduring
43-vertex lower bound in 1989, while later work by McKay, Radziszowski,
Angeltveit, and McKay reduced the upper bound to 46.

A prime-order automorphism with `c` moved cycles of length `p` has cycle type

```text
p^c 1^(43-pc).
```

For a vertex `v` in a graph from `R(5,5,43)`, its neighborhood contains
neither a `K4` nor an independent 5-set. Since `R(4,5)=25`, this gives
`d(v) <= 24`. The nonneighbors of `v` contain neither a `K5` nor an
independent 4-set, so `42-d(v) <= 24`. Hence every vertex satisfies

```text
18 <= d(v) <= 24.
```

A complete search at order 43 is not currently practical. This project
therefore addresses a finite structural subproblem: which prime-order
automorphisms could a hypothetical graph in `R(5,5,43)` admit?

## Starting Frontier And Longstanding Gap

Exoo published the lower bound 43 in 1989. McKay and Radziszowski proved the
upper bound 49 in 1997, Angeltveit and McKay improved it to 48 in 2018, and
their 2025 computation improved it to 46. The verified global frontier on
2026-09-08 was

```text
43 <= R(5,5) <= 46.
```

The lower endpoint had stood for 37 years. Existing prescribed-automorphism
campaigns had settled many symmetry classes, but the dated public audit
identified several small-support or unfinished prime-order cases for which a
short elementary exclusion or a retained, reproducible proof package was not
publicly available.

The project began from that scoped gap. It does not attempt to replace the
global order-43 search.

## Main Result

Elementary fixed-point, degree, and incidence arguments exclude 16
prime-order cycle types:

```text
2^c 1^(43-2c), c = 1,2,3
3^c 1^(43-3c), c = 1,2,3,4,5,7
5^c 1^(43-5c), c = 1,2,3
7^c 1^(43-7c), c = 1,2
11^1 1^32
13^1 1^30
```

Four of these elementary cases, the two order-7 types and the order-11 and
order-13 types, had already been covered by later computational campaigns.
As of 2026-09-08, the following 12 elementary exclusions were still marked
pending, uncovered, or unfinished in the audited public case lists and
coverage ledgers:

```text
2^c 1^(43-2c), 1 <= c <= 3
3^c 1^(43-3c), 1 <= c <= 5
3^7 1^22
5^c 1^(43-5c), 1 <= c <= 3
```

Two additional order-3 types are closed by proof-logged SAT:

- `3^6 1^25`, through four normalized orbit-CNF branches;
- `3^8 1^19`, through six canonical `t=2,3` branches and four
  matrix-split `t=4` branches.

The combined original result excludes 14 cycle types that the public case
lists and coverage ledgers audited through 2026-09-08 still marked pending,
uncovered, or unfinished: the 12 elementary cases above, `3^6 1^25`, and
`3^8 1^19`.

A targeted public search found no earlier completed exclusion or
independently checkable certificate for these 14 types. This is a dated
public-record resolution claim, not an absolute-priority or first-attempt
claim.

In particular:

```text
No graph on 43 vertices with clique number and independence number at most 4
admits an automorphism of cycle type 3^8 1^19.
```

## Method And Proof Architecture

### Elementary Prime-Order Exclusions

For prime `p >= 5`, choose a moved `p`-cycle `C`. Its induced graph is
neither complete nor empty, so it contains an edge and a nonedge. Every fixed
vertex is either complete or anticomplete to `C`. Fixed vertices complete to
`C` form a triangle-free and independent-5-free graph, while fixed vertices
anticomplete to `C` form a clique-5-free and independent-triple-free graph.
Using `R(3,5)=R(5,3)=14`, each set has at most 13 vertices. Therefore the
automorphism has at most 26 fixed vertices.

This excludes:

```text
5^c 1^(43-5c), c = 1,2,3
7^c 1^(43-7c), c = 1,2
11^1 1^32
13^1 1^30
```

For order 3, each moved cycle is a triangle or an independent triple. A
vertex in a triangle cycle has degree at most `3c+3`; a vertex in an
independent cycle has degree at least `39-3c`. The degree interval excludes
`c <= 4`. At `c=5`, equality forces triangle cycles to be complete to every
other moved cycle and independent cycles to be anticomplete. Mixed status is
inconsistent, while uniform status produces a clique or independent set on
15 vertices. Thus `c=5` is also impossible.

For order 2, a vertex in an edge pair has degree at most `2c+12`, while a
vertex in a nonedge pair has degree at least `30-2c`. This excludes `c=1,2`.
At `c=3`, equality again forces complete or empty crossings. Mixed status is
inconsistent, and uniform status produces a clique or independent set on six
vertices.

The arithmetic and equality cases are checked by:

```bash
python3 src/check_small_support.py
```

### Elementary `3^7 1^22` Exclusion

Let the moved cycles be `C_1,...,C_7`. Between distinct cycles `C_i` and
`C_j`, invariance partitions the nine possible edges into three perfect
matchings. Write `w_ij` for the number of those matchings present and
`q_i = sum_(j != i) w_ij`.

If `C_i` is a triangle, at most four fixed vertices are complete to it, so
the degree lower bound gives `q_i >= 12`. Two triangle cycles have
`w_ij <= 2`, since complete linkage creates a clique of size at least 5. If
`C_i` is independent, at least 18 fixed vertices are complete to it, so the
degree upper bound gives `q_i <= 6`. Two independent cycles have
`w_ij >= 1`, since empty linkage creates an independent set of size 6.

Suppose `t` moved cycles are triangles and `s=7-t` are independent. Summing
`q_i` over the triangle cycles gives a lower bound `12t`.
Triangle-triangle links contribute at most `4*C(t,2)` to this sum. Each
independent cycle uses at least `s-1` of its total weight on the other
independent cycles, so its total weight to triangle cycles is at most
`6-(s-1)=t`. Consequently,

```text
12t <= 4*C(t,2) + st = t(t+5).
```

This is impossible for `1 <= t <= 6`. All seven cycles therefore have the
same type. Complementing if necessary, take them all independent. Each of
the six intercycle weights at a moved cycle is at least 1 and their sum is at
most 6, so every weight is exactly 1. The degree upper bound then forces each
moved cycle to have exactly 18 fixed neighbors and four fixed nonneighbors.

For a fixed vertex `x`, let `Z_x` be the moved cycles anticomplete to `x`.
Counting by moved cycle gives:

```text
sum_x |Z_x| = 7 * 4 = 28.
```

If fixed vertices `x` and `y` are adjacent, their common neighborhood
contains neither a triangle nor an independent 5-set, and hence has at most
13 vertices by `R(3,5)=14`. Every moved cycle outside
`Z_x union Z_y` contributes all three vertices to that common neighborhood.
Thus `3(7-|Z_x union Z_y|) <= 13`, so
`|Z_x union Z_y| >= 3`.

Fixed vertices with `|Z_x| <= 1` are therefore pairwise nonadjacent and
number at most four. Every other fixed vertex has `|Z_x| >= 2`, which would
force:

```text
sum_x |Z_x| >= 2 * (22-4) = 36.
```

This contradicts the exact total 28 and excludes `3^7 1^22`.

### Certified `3^6 1^25` Exclusion

The encoder assigns one Boolean variable to each edge orbit under a fixed
permutation with six 3-cycles and 25 fixed points. For every 5-subset it adds
one clause forbidding a clique and one clause forbidding an independent set.
Exact counters impose the degree interval on one representative of each
moved vertex orbit and on every fixed vertex.

Choose the first fixed vertex as a root. Its adjacency to each 3-cycle is
constant. Arbitrary relabeling of the six cycles makes the adjacent cycles a
prefix, and complementation maps a prefix of length `k` to one of length
`6-k`. The branches `k=0,1,2,3` therefore cover all possibilities.

| Branch | Variables | Clauses | CNF SHA-256 | Compressed proof SHA-256 |
| ---: | ---: | ---: | --- | --- |
| 0 | 67,709 | 910,918 | `ac56dd4e6633f8aac9efea957799059bf98f5cf71507e800036c4ef9235821fc` | `c4365b7394386c4ac8a0669982d9afe7f0ee48aa312d641092d14e50ae831d60` |
| 1 | 67,709 | 910,918 | `2a92ff17114fbd30a0d6c152011c1cab1386839b7462b70c5ea95252c3b56089` | `e23f985a7dca17ecab5169dbdeba0d8e5f856e8c4ab89b8b0619dc368137f4bf` |
| 2 | 67,709 | 910,918 | `5543127a0f17e56c05cf9cdcd79935fd44433b6d2777c3d8c314361d4a96679c` | `6c570981d5c2c10cc609fa3e720e8a16dafcbc56715af4563a58c7b31f9a9489` |
| 3 | 67,709 | 910,918 | `e8a8e8453f45a0242c32a3c8c8cbca5b1743e34ae25f67829211223f79e4e688` | `ecc37245286371169abf5f6b5c3703d8ea464a685d253dd92534952a0eaac4c1` |

### Certified `3^8 1^19` Exclusion

Let `t` of the eight moved 3-cycles be triangles and let `s=8-t` be
independent triples. A triangle cycle has at most four fixed neighbors. An
independent cycle has at most four fixed nonneighbors. These are called
fixed-vertex exceptions.

When `t=1`, each of the seven independent cycles contributes at most four
fixed nonneighbor incidences, for a total at most 28. Any two fixed vertices
that each miss at most one independent cycle share at least five independent
cycles in their common neighborhood. They therefore cannot be adjacent,
since an adjacent pair has at most 13 common neighbors by `R(3,5)=14`.
There are at most four such fixed vertices, so the incidence total is at
least `2(19-4)=30`, a contradiction.

When `t=0`, the corresponding incidence total is at most 32. The same
common-neighborhood argument shows that fixed vertices missing at most one
moved cycle form an independent set of size at most four. The incidence
bound then forces at least two fixed vertices to miss no moved cycle. Each
has 24 moved neighbors and therefore no fixed neighbors. The other 17 fixed
vertices can contain neither a 5-clique nor an independent triple, contrary
to `R(5,3)=14`. Complementation excludes `t=7,8`.

It remains to consider `t=2,3,4`. For a triangle cycle `T_i`, write `a_i`
for its number of fixed neighbors and set `alpha_i=4-a_i`. For an independent
cycle `I_j`, write `b_j` for its number of fixed nonneighbors and set
`beta_j=4-b_j`. Let `u_i` be the amount by which the degree on `T_i` exceeds
18, and let `v_j` be the amount by which the degree on `I_j` falls below 24.
A triangle-triangle link has weight at most two; write its deficit from two
as `D`. An independent-independent link has weight at least one; write its
excess over one as `B`. Summing the mixed-link rows and columns in two ways
gives the exact identity

```text
sum alpha_i + sum beta_j + sum u_i + sum v_j
  + 2 sum D + 2 sum B = (t-4)^2.
```

Every term is a nonnegative integer. This yields all structural bounds used
by the encoder, including at least `32-(t-4)^2` exception incidences, at most
`floor((t-4)^2/2)` total same-type deviation, mixed total between
`2t(7-t)` and `(8-t)(t+2)`, triangle-row lower bound `14-2t`, and independent
column upper bound `t+2`.

At most 32 exception incidences are distributed over 19 fixed vertices, so
some fixed root has at most one exception. Relabeling cycles and
complementing the graph reduce all 2,304 low-exception configurations to
eight root branches:

```text
(2,0,0), (2,1,0), (2,0,1)
(3,0,0), (3,1,0), (3,0,1)
(4,0,0), (4,1,0)
```

The entries record the number of triangle cycles, the root's adjacent
triangle exceptions, and the root's nonadjacent independent exceptions.
The arithmetic audit assigns 162 configurations to the elementary cases and
2,142 to these certificate branches.

For `t=4`, the slack identity has zero right-hand side. Every triangle cycle
therefore has exactly four fixed neighbors and degree 18, every independent
cycle has exactly four fixed nonneighbors and degree 24, every
triangle-triangle link has weight two, every independent-independent link
has weight one, and every mixed row and column has total weight six.

A mixed weight cannot be three: otherwise the four fixed neighbors of its
triangle cycle equal the four fixed nonneighbors of its independent cycle,
but the first set is independent and the second is a clique. Complementation
excludes mixed weight zero. Every mixed weight is therefore one or two, with
two entries of each value in every row and column. The 90 labeled matrices
form exactly two classes under row and column permutations, represented by a
single 8-cycle and by two 4-cycles after subtracting one from every entry.

The four strengthened `t=4` formulas also encode three direct consequences:
two fixed vertices sharing a triangle exception are nonadjacent, two sharing
an independent exception are adjacent, and a triangle-exception set meets an
independent-exception set in at most one vertex. Seven independent cycle
rotations fix the matching phases on a spanning star. The `p1` branches
exclude zero-exception fixed signatures because any such vertex would
instead be chosen as the `p0` root.

The resulting retained certificate family consists of six canonical
`t=2,3` formulas and four matrix-split `t=4` formulas. Independent reference
encoders reproduce every clause. The ten solver branches are UNSAT, and
`drat-trim` has verified each compacted proof individually and in one
release-grade ten-branch replay.

## Verification And Evidence

The repository contains:

- executable arithmetic checks for the elementary theorem;
- unit and exhaustive small-instance tests for the orbit-CNF encoder;
- exhaustive audits of the c6 root patterns and all 2,304 low-exception c8
  configurations;
- independent DIMACS structure and hash checks;
- four compressed binary DRAT proof streams for `3^6 1^25`;
- ten compressed binary DRAT proof packages for `3^8 1^19`;
- original solver and checker logs; and
- machine-readable metadata, coverage records, hashes, and audits.

The c6 and c8 families have complete certificate manifests independently
reconstructed from regenerated formulas, retained proofs, solver records, and
audit files. Fresh builds from pinned clean `drat-trim` source verified all
four c6 branches and all ten c8 branches. The c6 replay covers 56,884,692
compressed bytes and 159,015,979 decompressed bytes; its record SHA-256 is
`6815224208794b686c633b0d601bccbcfbd8d580dcaee991b4e8f2ec5af3d934`.
The c8 replay covers 557,888,932 compressed bytes and 2,730,397,896
decompressed bytes; its record SHA-256 is
`0de9d8c9c66901ed326a13d6b2e54255b19556321f26c8d03e8ec13999611ddf`.
The inspected PDF is committed, hash-bound, and reproducible byte for byte
under the recorded source-date epoch. The corrected snapshot passed separate
mathematical and release-integrity reviews. Hosted CI is still pending.

The c8 evidence records distinguish original solver output from retained
proof cores and disclose whether exact artifact hashes came from the original
solver log or from a labeled post-run attestation. Formula generation and
proof checking are CPU-bound and require no GPU. Exact formula sizes, proof
sizes, hashes, and recorded runtimes are retained under
`evidence/orbit-p3-c6/` and `evidence/orbit-p3-c8/`. The release-grade replay
records, fresh checker binaries, checker-build logs, and per-branch logs are
retained under `evidence/replay-c6/` and `evidence/replay-c8/`.

The verified release manifest binds the source, documentation, formulas,
proof packages, retained replay records and logs, audits, and committed report
to one candidate snapshot.

## Reproduction

Install the development requirements and run the deterministic test suite:

```bash
python3 -m pip install -r requirements-dev.txt
make test
python3 src/check_small_support.py
```

Regenerate the audited CNFs and verify the certificate families with:

```bash
make verify-certificates
```

The certificate target reconstructs and checks the complete c8 certificate
manifest before any proof replay begins.

Freshly replay all 14 retained proofs with a local `drat-trim` checkout:

```bash
make verify-proofs DRAT_TRIM=/path/to/drat-trim
```

The proof target requires that executable to reside in a source checkout at
the pinned commit recorded in `docs/REPRODUCIBILITY.md`. The c8 replay builds
its own fresh checker from that clean source before checking the ten proofs.

Runtime depends on processor speed and current load. The proof replay is
CPU-bound and requires sufficient local storage for regenerated formulas and
streamed proof checking.

## Claims

The repository claims the stated elementary exclusions and the two scoped
certificate-backed order-3 exclusions. The original contribution consists
of the 12 elementary cases and the certified exclusions of `3^6 1^25` and
`3^8 1^19` identified above.

The novelty statement is based on a targeted search of public literature and
repositories available through 2026-09-08. It is limited to the audited
public record and does not assert absolute priority. The exact claim boundary
is recorded in `docs/CLAIMS.md` and `research/claim.json`.

## Limitations And Nonclaims

The project does not determine `R(5,5)`, improve the global interval
`43 <= R(5,5) <= 46`, construct a 43-vertex Ramsey graph, prove that every
hypothetical graph is asymmetric, or exclude all nontrivial automorphisms.
Graphs with trivial automorphism group and many remaining order-2, order-3,
and order-5 cycle types are not excluded.

The computation is proof-checked but not formally verified in a proof
assistant. The encoder, structural reductions, artifact-binding code, and
proof checker remain within the computational trust boundary.

The public-source audit does not establish priority over unpublished,
inaccessible, or unindexed work.

## Significance And Use

The result removes a finite set of symmetry classes from any future
`R(5,5)` search. The elementary fixed-point lemma replaces several
certificate-heavy cases with a short reusable argument, while the orbit-CNF
and proof-package pipeline gives a reproducible route for harder cycle
types.

These exclusions can reduce symmetry-aware search spaces, provide regression
targets for independent encoders, and clarify which automorphism groups still
deserve computational effort. The c8 slack identity and matrix
classification may also be useful in related prescribed-automorphism
problems.

## Remaining Work And Future Directions

Before public release, the project still requires:

- hosted replay and candidate CI on the committed release snapshot;
- tag-bound source and checksum asset verification;
- public repository release; and
- DOI archival.

The strongest next mathematical order-3 route is `3^9 1^16`, followed by the
remaining order-2 and order-5 branches. Longer-term work includes reducing
the checker trust boundary and reconstructing the elementary and certificate
arguments in a proof assistant.

## Repository Layout

```text
docs/       claims, prior art, reproducibility, and next research steps
evidence/   retained proofs, logs, metadata, hashes, and audits
paper/      technical report source and submission metadata
research/   machine-readable claim and release-gate records
src/        elementary checker and orbit-CNF generator
tests/      semantic, regression, and package-boundary tests
tools/      independent audits, proof replay, and release tooling
```

## Publication Citation And Archive

The permanent public repository is
[`ruturajr-raval/ramsey-number-5-5`](https://github.com/ruturajr-raval/ramsey-number-5-5).
The repository is public, but no tagged release or DOI has yet been assigned.

Package status: not yet released.

Citation metadata is prepared in `CITATION.cff`, archive metadata is prepared
in `.zenodo.json`, technical report source and submission metadata are in
`paper/`, and the release dossier is in `PUBLICATION.md`. Final citation and
archive links will be added only after the release gate, hosted CI, and
archival checks pass.

## Authorship

**Ruturaj R Raval**

Independent Researcher

ORCID: [0000-0003-4930-8981](https://orcid.org/0000-0003-4930-8981)

## Licensing And Provenance

Project-original software, proofs, evidence records, and documentation are
MIT licensed under the root `LICENSE`.

The two retained `drat-trim` checker executables remain under their upstream
MIT license, reproduced at `third_party/drat-trim/LICENSE`. Other third-party
solvers, papers, and public coverage records are referenced but not
relicensed. Their versions, commits, and roles in the verification chain are
recorded in the reproducibility and evidence materials.

## References

1. F. P. Ramsey, "On a problem of formal logic," Proceedings of the London
   Mathematical Society s2-30(1), 264-286, 1930.
2. R. E. Greenwood and A. M. Gleason, "Combinatorial relations and
   chromatic graphs," Canadian Journal of Mathematics 7, 1-7, 1955.
3. Geoffrey Exoo, "A lower bound for R(5,5)," Journal of Graph Theory 13(1),
   97-98, 1989.
4. Brendan D. McKay and Stanislaw P. Radziszowski, "R(4,5)=25," Journal of
   Graph Theory 19(3), 309-322, 1995.
5. Brendan D. McKay and Stanislaw P. Radziszowski, "Subgraph counting
   identities and Ramsey numbers," Journal of Combinatorial Theory, Series B
   69(2), 193-209, 1997.
6. Vigleik Angeltveit and Brendan D. McKay, "R(5,5) <= 48," Journal of Graph
   Theory 89(1), 5-13, 2018.
7. Vigleik Angeltveit and Brendan D. McKay, "R(5,5) <= 46,"
   [arXiv:2409.15709](https://arxiv.org/abs/2409.15709), version 2, 2025.
8. Current public prescribed-automorphism audit:
   [wustep/maths](https://github.com/wustep/maths/tree/main/problems/ramsey-r55).

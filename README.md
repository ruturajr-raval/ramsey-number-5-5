# Prime-Order Automorphism Exclusions for Ramsey `(5,5,43)` Graphs

## Project Overview

### Project Metadata

| Field | Value |
| --- | --- |
| Author | Ruturaj R Raval |
| Affiliation | Independent Researcher |
| ORCID | [0000-0003-4930-8981](https://orcid.org/0000-0003-4930-8981) |
| Field | Ramsey theory, graph automorphisms, and proof-logged SAT |
| Problem | Restrict prime-order automorphisms of hypothetical Ramsey `(5,5,43)` graphs |
| Current result | Twelve previously uncovered automorphism cycle types are excluded: eleven by an elementary theorem and `3^6 1^25` by four checked DRAT certificates |
| Result type | Scoped structural theorem and certified finite exclusion |
| Release | not yet released |
| Version DOI | not yet assigned |
| Concept DOI | not yet assigned |
| License | MIT |

### Problem And Context

The diagonal Ramsey number `R(5,5)` is the least integer `n` such that every
graph on `n` vertices contains a clique of size 5 or an independent set of
size 5. Exoo published the lower bound 43 in 1989. McKay and Radziszowski
proved the upper bound 49 in 1997, Angeltveit and McKay improved it to 48 in
2018, and their 2025 computation improved it to 46. The verified frontier on
2026-09-07 was therefore

```text
43 <= R(5,5) <= 46.
```

The lower endpoint had stood for 37 years. A complete search at order 43 is
not currently practical, so this project studies a finite structural
subproblem: which prime-order automorphisms could a hypothetical graph on 43
vertices have while avoiding both a clique and an independent set of size 5?

### Work And Verified Outcome

An elementary fixed-point and degree argument excludes 15 prime-order cycle
types. Four of those cases had already been covered by later computational
campaigns, while the following 11 were still uncovered in the audited public
coverage:

```text
2^c 1^(43-2c), 1 <= c <= 3
3^c 1^(43-3c), 1 <= c <= 5
5^c 1^(43-5c), 1 <= c <= 3
```

The next order-3 type, `3^6 1^25`, is closed by an independent orbit-CNF
encoder. Relabeling the six moved cycles and complementing the graph reduce
all 64 fixed-root adjacency patterns to four branches. Kissat reported each
branch UNSAT, and `drat-trim` independently verified every retained binary
DRAT proof. The combined original result excludes 12 cycle types that the
dated public audits left unresolved.

### Claim Boundary

The project proves only the stated automorphism exclusions. It does not
determine `R(5,5)`, improve the global interval, construct a 43-vertex Ramsey
graph, prove that every hypothetical graph is asymmetric, or exclude all
nontrivial automorphisms. Graphs with trivial automorphism group and many
remaining order-2, order-3, and order-5 cycle types remain possible.

The novelty statement is based on a targeted search of public literature and
repositories available through 2026-09-07. It is not a claim of priority over
unpublished, inaccessible, or unindexed work. The computation is
proof-checked but not formally verified in a proof assistant.

### Verification And Reproduction

The repository contains:

- executable arithmetic checks for the elementary theorem;
- unit and exhaustive small-instance tests for the orbit-CNF encoder;
- an exhaustive audit of all 64 branch patterns;
- independent DIMACS structure and hash checks;
- four compressed binary DRAT proofs;
- original solver and checker logs; and
- a machine-readable certificate manifest.

Run the deterministic checks and regenerate all four CNFs:

```bash
python3 -m pip install -r requirements-dev.txt
make test
make verify-certificates
```

Freshly replay all four proofs with a local `drat-trim` executable:

```bash
make verify-proofs DRAT_TRIM=/path/to/drat-trim
```

The proof target requires that executable to reside in a source checkout at
the pinned commit recorded in `docs/REPRODUCIBILITY.md`.

The regenerated formulas total about 134 MB. Retained compressed proofs total
about 57 MB and expand to about 159 MB. Formula generation and proof checking
are CPU-bound, require no GPU, and fit a commodity workstation. Exact hashes
and recorded runtimes are in
`evidence/orbit-p3-c6/certificate-manifest.json`.

### Significance, Limitations, And Future Work

The result removes a finite set of symmetry classes from any future
`R(5,5)` search. The elementary fixed-point lemma replaces several
certificate-heavy cases with a short reusable argument, while the
certificate pipeline gives a reproducible route for harder cycle types.
These reductions can shrink symmetry-aware searches and clarify which
automorphism groups still deserve computational effort.

The main limitation is scope: an asymmetric graph is untouched, and the
global interval remains unchanged. The strongest next route is to close more
order-3 types, followed by the remaining order-2 and order-5 branches. A
public release requires a complete package review, fresh certificate replay
on a clean environment, a built and inspected paper, and a refreshed
prior-art audit.

### Release, Citation, And Author

This package is not yet released or archived. The research workbench is
maintained at
[`ruturajr-raval/ramsey-number-5-5-research-workbench`](https://github.com/ruturajr-raval/ramsey-number-5-5-research-workbench).
Citation metadata is prepared in `CITATION.cff`, and archive metadata is
prepared in `.zenodo.json`.

Project-original software, proofs, evidence records, and documentation are
MIT licensed. Third-party solvers, proof checkers, papers, and public
coverage records are referenced but not relicensed. The author is
Ruturaj R Raval, Independent Researcher, ORCID
[`0000-0003-4930-8981`](https://orcid.org/0000-0003-4930-8981).

## Detailed Technical Record

### Definitions

Write `R(5,5,n)` for the class of finite simple undirected graphs on `n`
vertices with clique number and independence number at most 4. A
prime-order automorphism with `c` moved cycles of length `p` has cycle type

```text
p^c 1^(43-pc).
```

### Degree Interval

For a vertex `v` in a graph from `R(5,5,43)`, its neighborhood contains
neither a `K4` nor an independent 5-set. Since `R(4,5)=25`, this gives
`d(v) <= 24`. The nonneighbors of `v` contain neither a `K5` nor an
independent 4-set, so `42-d(v) <= 24`. Hence every vertex satisfies

```text
18 <= d(v) <= 24.
```

### Elementary Exclusions

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

### Repository Layout

```text
docs/       claims, prior art, reproducibility, and next research steps
evidence/   retained proofs, logs, metadata, hashes, and audits
paper/      technical report source and submission metadata
research/   machine-readable claim and release-gate records
src/        elementary checker and orbit-CNF generator
tests/      semantic, regression, and package-boundary tests
tools/      independent audits, proof replay, and release tooling
```

### References

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
6. Current public prescribed-automorphism audit:
   [wustep/maths](https://github.com/wustep/maths/tree/main/problems/ramsey-r55).

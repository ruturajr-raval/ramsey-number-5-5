# Claim Ledger

Audit date: 2026-09-08

## Supported Claims

### C1 - Degree interval

Every finite simple graph on 43 vertices with clique number and independence
number at most 4 has every vertex degree in `[18,24]`.

Basis: `R(4,5)=R(5,4)=25`.

### C2 - Elementary fixed-point theorem

No such graph has a prime-order automorphism with any of these 16 cycle
types:

```text
2^c 1^(43-2c), 1 <= c <= 3
3^c 1^(43-3c), 1 <= c <= 5
3^7 1^22
5^c 1^(43-5c), 1 <= c <= 3
7^c 1^(43-7c), 1 <= c <= 2
11^1 1^32
13^1 1^30
```

Evidence:

- proof in `paper/main.tex`;
- executable arithmetic audit in `src/check_small_support.py`; and
- focused regression tests in `tests/test_small_support.py`.

### C3 - Original elementary delta

The targeted public audit through 2026-09-08 found the following 12 cycle
types still marked pending, uncovered, or unfinished before this work:

```text
2^c 1^(43-2c), 1 <= c <= 3
3^c 1^(43-3c), 1 <= c <= 5
3^7 1^22
5^c 1^(43-5c), 1 <= c <= 3
```

The order-7, order-11, and order-13 consequences in C2 are shorter
elementary reproofs of cases already covered computationally.

### C4 - Certified `3^6 1^25` exclusion

No such graph has an automorphism of cycle type `3^6 1^25`.

Evidence:

- all 64 root adjacency patterns reduce to branches `0,1,2,3`;
- each branch CNF has 67,709 variables and 910,918 clauses;
- every regenerated CNF matches its retained SHA-256 digest;
- every compressed DRAT proof matches its retained digest; and
- `drat-trim` verifies all four proofs.

The central record is
`evidence/orbit-p3-c6/certificate-manifest.json`.

### C5 - Elementary `3^7 1^22` exclusion

No such graph has an automorphism of cycle type `3^7 1^22`.

Evidence:

- mixed triangle and independent moved cycles violate the degree sums;
- after complementation, every pair of moved cycles has one matching and
  every moved cycle has exactly four fixed nonneighbors;
- fixed vertices missing at most one moved cycle are pairwise nonadjacent;
- at most four such vertices can exist, forcing at least 36 fixed-cycle
  nonneighbor incidences although the exact total is 28; and
- the deterministic arithmetic consistency audit is in
  `src/check_small_support.py`.

### C6 - Certified `3^8 1^19` exclusion

No such graph has an automorphism of cycle type `3^8 1^19`.

Evidence:

- the internal-type counts `0,1,7,8` are excluded by elementary incidence
  arguments;
- complementation and a low-exception fixed root reduce the remaining cases
  to eight normalized root branches;
- an exact slack identity supplies the encoded exception, same-type, mixed
  row, and mixed column bounds;
- the two `t=4` root branches split into four branches using the complete
  classification of 90 mixed-link matrices into two equivalence classes;
- six canonical `t=2,3` formulas and four strengthened `t=4` formulas match
  independent reference encoders exactly;
- all ten branches are UNSAT and every retained compact DRAT proof passes
  independent `drat-trim` replay; and
- the central record is
  `evidence/orbit-p3-c8/certificate-manifest.json`.

### C7 - Combined original result

The project excludes 14 cycle types that the dated public audits listed as
uncovered or unfinished:

```text
2^c 1^(43-2c), 1 <= c <= 3
3^c 1^(43-3c), 1 <= c <= 8
5^c 1^(43-5c), 1 <= c <= 3
```

A targeted public search found no earlier completed exclusion or
independently checkable certificate for these types. This is a dated
public-record resolution claim, not an absolute-priority or first-attempt
claim.

### C8 - Total demonstrated exclusions

The package demonstrates 18 distinct prime-order automorphism cycle-type
exclusions in total: 16 elementary exclusions from C2 and the two additional
certificate-backed exclusions from C4 and C6. Of these 18, the 14 types in C7
form the original delta relative to the dated public audit. The remaining
four are elementary reproofs of cases already covered computationally.

## Reproduced Or Prior Results

- `43 <= R(5,5) <= 46`;
- `R(4,5)=25`;
- `R(3,5)=14`;
- later public certificates excluding all order-7 types and applicable prime
  orders at least 11; and
- the standard orbit-variable and DRAT proof-checking methodology.

## Explicit Nonclaims

- The project does not determine `R(5,5)`.
- The project does not improve the global lower or upper bound.
- The project does not construct a graph in `R(5,5,43)`.
- The project does not prove that a hypothetical graph is asymmetric.
- The project does not exclude every order-2, order-3, or order-5 type.
- The project does not classify all graphs at order 43.
- The project does not claim formal proof-assistant verification.
- The project does not claim priority over unavailable or unindexed work.

## Announcement Gate

The theorem is suitable for announcement only after a clean-environment proof
replay, paper build and inspection, refreshed prior-art audit, independent
package review, tagged release, and durable archive all pass.

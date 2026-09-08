PYTHON ?= python3
CC ?= cc
DRAT_TRIM ?= drat-trim
DRAT_TRIM_COMMIT := 2e3b2dc0ecf938addbd779d42877b6ed69d9a985
DRAT_TRIM_SOURCE ?= $(patsubst %/,%,$(dir $(DRAT_TRIM)))
SOURCE_DATE_EPOCH ?= 1788825600

BUILD := build
RELEASE_REF ?= HEAD
RELEASE_TAG ?=
RELEASE_TAG_OPTION := $(if $(strip $(RELEASE_TAG)),--tag $(RELEASE_TAG),)
RELEASE_PDF := paper/ramsey-number-5-5-paper-v0.1.0.pdf

C6_CNF_BUILD := $(BUILD)/orbit-p3-c6
C6_REPLAY_BUILD := $(BUILD)/proof-replay-c6
C6_EVIDENCE := evidence/orbit-p3-c6
C6_BRANCHES := 0 1 2 3
C6_CNFS := $(foreach branch,$(C6_BRANCHES),$(C6_CNF_BUILD)/p3-c6-k$(branch).cnf)

C8_CNF_BUILD := $(BUILD)/verification/orbit-p3-c8
C8_T4_CNF_BUILD := $(BUILD)/verification/orbit-p3-c8-t4-split
C8_REPLAY_BUILD := $(BUILD)/proof-replay-c8
C8_EVIDENCE := evidence/orbit-p3-c8
C8_CANONICAL_STEMS := \
	p3-c8-t2-p0-z0 \
	p3-c8-t2-p1-z0 \
	p3-c8-t2-p0-z1 \
	p3-c8-t3-p0-z0 \
	p3-c8-t3-p1-z0 \
	p3-c8-t3-p0-z1 \
	p3-c8-t4-p0-z0 \
	p3-c8-t4-p1-z0
C8_T4_STEMS := \
	p3-c8-t4-p0-z0-mtwo-c4 \
	p3-c8-t4-p0-z0-mc8 \
	p3-c8-t4-p1-z0-mtwo-c4 \
	p3-c8-t4-p1-z0-mc8
C8_CANONICAL_CNFS := $(addprefix $(C8_CNF_BUILD)/,$(addsuffix .cnf,$(C8_CANONICAL_STEMS)))
C8_T4_CNFS := $(addprefix $(C8_T4_CNF_BUILD)/,$(addsuffix .cnf,$(C8_T4_STEMS)))

.PHONY: all test verify-text verify-elementary verify-c6-elementary \
	verify-c8-elementary build-cnfs regenerate-cnfs verify-cnfs \
	build-c6-cnfs regenerate-c6-cnfs verify-c6-cnfs \
	build-c8-cnfs regenerate-c8-cnfs verify-c8-cnfs \
	verify-certificates verify-c6-certificates verify-c8-certificates \
	verify-proofs verify-c6-proofs verify-c8-proofs \
	verify-release-candidate verify-release-gate \
	verify-release-manifest release-manifest \
	release-assets verify-release-assets paper paper-tectonic clean

all: test verify-text verify-elementary verify-certificates

test:
	PYTHONPATH=src:tools $(PYTHON) -m unittest discover -s tests -v

verify-text:
	$(PYTHON) tools/check_repository_text.py

verify-elementary: verify-c6-elementary verify-c8-elementary

verify-c6-elementary:
	mkdir -p $(BUILD)
	$(PYTHON) src/check_small_support.py > $(BUILD)/small-support.json
	cmp $(BUILD)/small-support.json evidence/small-support.json
	$(PYTHON) tools/verify_branch_coverage.py \
		--cycles 6 \
		--output $(BUILD)/branch-coverage.json \
		> $(BUILD)/branch-coverage.stdout.json
	cmp $(BUILD)/branch-coverage.json $(C6_EVIDENCE)/branch-coverage.json

verify-c8-elementary:
	mkdir -p $(BUILD)
	$(PYTHON) tools/verify_c8_branch_coverage.py \
		--output $(BUILD)/c8-branch-coverage.json \
		> $(BUILD)/c8-branch-coverage.stdout.json
	cmp $(BUILD)/c8-branch-coverage.json \
		$(C8_EVIDENCE)/branch-coverage.json
	$(PYTHON) tools/verify_c8_t4_reduction.py \
		--output $(BUILD)/c8-t4-matrix-reduction.json \
		> $(BUILD)/c8-t4-matrix-reduction.stdout.json
	cmp $(BUILD)/c8-t4-matrix-reduction.json \
		$(C8_EVIDENCE)/t4-matrix-reduction.json

$(C6_CNF_BUILD)/p3-c6-k%.cnf: src/orbit_cnf.py
	mkdir -p $(C6_CNF_BUILD)
	$(PYTHON) src/orbit_cnf.py \
		--prime 3 \
		--cycles 6 \
		--degree-lower 18 \
		--degree-upper 24 \
		--root-adjacent-cycles $* \
		--output $@ \
		--metadata $(C6_CNF_BUILD)/p3-c6-k$*.json \
		> $(C6_CNF_BUILD)/p3-c6-k$*.generation.log

build-c6-cnfs: $(C6_CNFS)

regenerate-c6-cnfs:
	rm -rf $(C6_CNF_BUILD)
	$(MAKE) build-c6-cnfs PYTHON="$(PYTHON)"

verify-c6-cnfs: regenerate-c6-cnfs
	cmp $(C6_CNF_BUILD)/p3-c6-k0.json $(C6_EVIDENCE)/p3-c6-k0.json
	cmp $(C6_CNF_BUILD)/p3-c6-k1.json $(C6_EVIDENCE)/p3-c6-k1.json
	cmp $(C6_CNF_BUILD)/p3-c6-k2.json $(C6_EVIDENCE)/p3-c6-k2.json
	cmp $(C6_CNF_BUILD)/p3-c6-k3.json $(C6_EVIDENCE)/p3-c6-k3.json
	$(PYTHON) tools/verify_branch_artifacts.py \
		$(C6_CNF_BUILD) \
		--output $(C6_CNF_BUILD)/cnf-audit.json \
		> $(C6_CNF_BUILD)/cnf-audit.stdout.json
	cmp $(C6_CNF_BUILD)/cnf-audit.json $(C6_EVIDENCE)/cnf-audit.json

define C8_CANONICAL_RULE
$(C8_CNF_BUILD)/p3-c8-t$(1)-p$(2)-z$(3).cnf: src/orbit_cnf.py
	mkdir -p $(C8_CNF_BUILD)
	$(PYTHON) src/orbit_cnf.py \
		--prime 3 \
		--cycles 8 \
		--degree-lower 18 \
		--degree-upper 24 \
		--triangle-cycles $(1) \
		--root-adjacent-triangle-cycles $(2) \
		--root-nonadjacent-independent-cycles $(3) \
		--order-three-eight-structure \
		--output $(C8_CNF_BUILD)/p3-c8-t$(1)-p$(2)-z$(3).cnf \
		--metadata $(C8_CNF_BUILD)/p3-c8-t$(1)-p$(2)-z$(3).json \
		> $(C8_CNF_BUILD)/p3-c8-t$(1)-p$(2)-z$(3).generation.log
endef

$(eval $(call C8_CANONICAL_RULE,2,0,0))
$(eval $(call C8_CANONICAL_RULE,2,1,0))
$(eval $(call C8_CANONICAL_RULE,2,0,1))
$(eval $(call C8_CANONICAL_RULE,3,0,0))
$(eval $(call C8_CANONICAL_RULE,3,1,0))
$(eval $(call C8_CANONICAL_RULE,3,0,1))
$(eval $(call C8_CANONICAL_RULE,4,0,0))
$(eval $(call C8_CANONICAL_RULE,4,1,0))

define C8_T4_RULE
$(C8_T4_CNF_BUILD)/p3-c8-t4-p$(1)-z0-m$(2).cnf: src/orbit_cnf.py
	mkdir -p $(C8_T4_CNF_BUILD)
	$(PYTHON) src/orbit_cnf.py \
		--prime 3 \
		--cycles 8 \
		--degree-lower 18 \
		--degree-upper 24 \
		--triangle-cycles 4 \
		--root-adjacent-triangle-cycles $(1) \
		--root-nonadjacent-independent-cycles 0 \
		--order-three-eight-structure \
		--t4-mixed-matrix $(2) \
		$(3) \
		--output $(C8_T4_CNF_BUILD)/p3-c8-t4-p$(1)-z0-m$(2).cnf \
		--metadata $(C8_T4_CNF_BUILD)/p3-c8-t4-p$(1)-z0-m$(2).json \
		> $(C8_T4_CNF_BUILD)/p3-c8-t4-p$(1)-z0-m$(2).generation.log
endef

$(eval $(call C8_T4_RULE,0,two-c4,))
$(eval $(call C8_T4_RULE,0,c8,))
$(eval $(call C8_T4_RULE,1,two-c4,--exclude-zero-fixed-signatures))
$(eval $(call C8_T4_RULE,1,c8,--exclude-zero-fixed-signatures))

build-c8-cnfs: $(C8_CANONICAL_CNFS) $(C8_T4_CNFS)

regenerate-c8-cnfs:
	rm -rf $(C8_CNF_BUILD) $(C8_T4_CNF_BUILD)
	$(MAKE) build-c8-cnfs PYTHON="$(PYTHON)"

verify-c8-cnfs: regenerate-c8-cnfs
	@for stem in $(C8_CANONICAL_STEMS); do \
		cmp "$(C8_CNF_BUILD)/$$stem.json" \
			"$(C8_EVIDENCE)/$$stem.json"; \
	done
	@for stem in $(C8_T4_STEMS); do \
		cmp "$(C8_T4_CNF_BUILD)/$$stem.json" \
			"$(C8_EVIDENCE)/$$stem.json"; \
	done
	$(PYTHON) tools/verify_c8_branch_artifacts.py \
		$(C8_CNF_BUILD) \
		--output $(C8_CNF_BUILD)/cnf-audit.json \
		> $(C8_CNF_BUILD)/cnf-audit.stdout.json
	cmp $(C8_CNF_BUILD)/cnf-audit.json \
		$(C8_EVIDENCE)/canonical-cnf-audit.json
	$(PYTHON) tools/verify_c8_formula_semantics.py \
		$(C8_CNF_BUILD) \
		--output $(C8_CNF_BUILD)/formula-semantics-audit.json \
		> $(C8_CNF_BUILD)/formula-semantics-audit.stdout.json
	cmp $(C8_CNF_BUILD)/formula-semantics-audit.json \
		$(C8_EVIDENCE)/canonical-formula-semantics-audit.json
	$(PYTHON) tools/verify_c8_t4_formula_semantics.py \
		$(C8_T4_CNF_BUILD) \
		--output $(C8_T4_CNF_BUILD)/formula-semantics-audit.json \
		> $(C8_T4_CNF_BUILD)/formula-semantics-audit.stdout.json
	cmp $(C8_T4_CNF_BUILD)/formula-semantics-audit.json \
		$(C8_EVIDENCE)/t4-formula-semantics-audit.json

build-cnfs: build-c6-cnfs build-c8-cnfs

regenerate-cnfs: regenerate-c6-cnfs regenerate-c8-cnfs

verify-cnfs: verify-c6-cnfs verify-c8-cnfs

verify-c6-certificates: verify-c6-elementary verify-c6-cnfs
	$(PYTHON) tools/verify_certificates.py \
		$(C6_CNF_BUILD) \
		$(C6_EVIDENCE) \
		--coverage $(C6_EVIDENCE)/branch-coverage.json \
		--cnf-audit $(C6_EVIDENCE)/cnf-audit.json \
		--expected-manifest $(C6_EVIDENCE)/certificate-manifest.json \
		--output $(BUILD)/reconstructed-c6-certificate-manifest.json \
		> $(BUILD)/reconstructed-c6-certificate-manifest.stdout.json

verify-c8-certificates: verify-c8-elementary verify-c8-cnfs
	$(PYTHON) tools/verify_c8_certificates.py \
		$(C8_CNF_BUILD) \
		$(C8_T4_CNF_BUILD) \
		$(C8_EVIDENCE) \
		--coverage $(C8_EVIDENCE)/branch-coverage.json \
		--canonical-cnf-audit \
			$(C8_EVIDENCE)/canonical-cnf-audit.json \
		--canonical-semantic-audit \
			$(C8_EVIDENCE)/canonical-formula-semantics-audit.json \
		--t4-reduction $(C8_EVIDENCE)/t4-matrix-reduction.json \
		--t4-semantic-audit \
			$(C8_EVIDENCE)/t4-formula-semantics-audit.json \
		--expected-manifest $(C8_EVIDENCE)/certificate-manifest.json \
		--output $(BUILD)/reconstructed-c8-certificate-manifest.json \
		> $(BUILD)/reconstructed-c8-certificate-manifest.stdout.json

verify-certificates: verify-c6-certificates verify-c8-certificates

verify-c6-proofs: verify-c6-certificates
	test -x "$(DRAT_TRIM)"
	test "$$(git -C "$(DRAT_TRIM_SOURCE)" rev-parse HEAD)" = \
		"$(DRAT_TRIM_COMMIT)"
	mkdir -p $(C6_REPLAY_BUILD)
	$(PYTHON) tools/replay_proofs.py \
		$(C6_CNF_BUILD) \
		$(C6_EVIDENCE) \
		--checker-source "$(DRAT_TRIM_SOURCE)" \
		--fresh-checker-build \
		--cc "$(CC)" \
		--certificate-manifest $(C6_EVIDENCE)/certificate-manifest.json \
		--log-directory $(C6_REPLAY_BUILD) \
		--output $(C6_REPLAY_BUILD)/fresh-proof-replay.json \
		> $(C6_REPLAY_BUILD)/fresh-proof-replay.stdout.json

verify-c8-proofs: verify-c8-certificates
	test -x "$(DRAT_TRIM)"
	test "$$(git -C "$(DRAT_TRIM_SOURCE)" rev-parse HEAD)" = \
		"$(DRAT_TRIM_COMMIT)"
	mkdir -p $(C8_REPLAY_BUILD)
	$(PYTHON) tools/replay_c8_proofs.py \
		$(C8_CNF_BUILD) \
		--proof-directory $(C8_EVIDENCE) \
		--solver-log-directory $(C8_EVIDENCE) \
		--checker-source "$(DRAT_TRIM_SOURCE)" \
		--fresh-checker-build \
		--cc "$(CC)" \
		--t4-split-artifact-directory $(C8_T4_CNF_BUILD) \
		--t4-split-proof-directory $(C8_EVIDENCE) \
		--t4-split-solver-log-directory $(C8_EVIDENCE) \
		--certificate-manifest $(C8_EVIDENCE)/certificate-manifest.json \
		--log-directory $(C8_REPLAY_BUILD) \
		--output $(C8_REPLAY_BUILD)/fresh-proof-replay.json \
		> $(C8_REPLAY_BUILD)/fresh-proof-replay.stdout.json

verify-proofs: verify-c6-proofs verify-c8-proofs

verify-release-candidate:
	$(PYTHON) tools/verify_release_gate.py \
		--mode candidate \
		--ref $(RELEASE_REF) \
		--output $(BUILD)/release-candidate-evidence.json

verify-release-gate: verify-release-manifest verify-release-assets
	$(PYTHON) tools/verify_release_gate.py \
		--mode final \
		--ref $(RELEASE_REF) $(RELEASE_TAG_OPTION) \
		--output $(BUILD)/release-final-evidence.json

paper:
	mkdir -p $(BUILD)/paper
	SOURCE_DATE_EPOCH=$(SOURCE_DATE_EPOCH) \
		pdflatex -halt-on-error -output-directory=$(BUILD)/paper paper/main.tex
	SOURCE_DATE_EPOCH=$(SOURCE_DATE_EPOCH) \
		pdflatex -halt-on-error -output-directory=$(BUILD)/paper paper/main.tex
	$(PYTHON) tools/record_paper_build.py \
		--source paper/main.tex \
		--pdf $(BUILD)/paper/main.pdf \
		--log $(BUILD)/paper/main.log \
		--output $(BUILD)/paper/paper-build.json

paper-tectonic:
	test -n "$(TECTONIC)"
	mkdir -p $(BUILD)/paper
	SOURCE_DATE_EPOCH=$(SOURCE_DATE_EPOCH) \
		$(TECTONIC) --outdir $(BUILD)/paper --keep-logs paper/main.tex
	$(PYTHON) tools/record_paper_build.py \
		--source paper/main.tex \
		--pdf $(BUILD)/paper/main.pdf \
		--log $(BUILD)/paper/main.log \
		--output $(BUILD)/paper/paper-build.json
	cmp $(BUILD)/paper/main.pdf $(RELEASE_PDF)

release-assets:
	test -f $(BUILD)/paper/main.pdf
	$(PYTHON) tools/build_release_assets.py \
		--ref $(RELEASE_REF) $(RELEASE_TAG_OPTION) \
		--paper $(BUILD)/paper/main.pdf

verify-release-assets:
	$(PYTHON) tools/build_release_assets.py \
		--check \
		--ref $(RELEASE_REF) $(RELEASE_TAG_OPTION) \
		--paper $(BUILD)/paper/main.pdf

verify-release-manifest:
	$(PYTHON) tools/release_manifest.py --check

release-manifest:
	$(PYTHON) tools/release_manifest.py --write

clean:
	rm -rf $(BUILD)

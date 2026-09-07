PYTHON ?= python3
DRAT_TRIM ?= drat-trim
DRAT_TRIM_COMMIT := 2e3b2dc0ecf938addbd779d42877b6ed69d9a985
DRAT_TRIM_SOURCE ?= $(patsubst %/,%,$(dir $(DRAT_TRIM)))

BUILD := build
CNF_BUILD := $(BUILD)/orbit-p3-c6
REPLAY_BUILD := $(BUILD)/proof-replay
EVIDENCE := evidence/orbit-p3-c6
BRANCHES := 0 1 2 3
CNFS := $(foreach branch,$(BRANCHES),$(CNF_BUILD)/p3-c6-k$(branch).cnf)

.PHONY: all test verify-text verify-elementary build-cnfs regenerate-cnfs \
	verify-cnfs \
	verify-certificates verify-proofs verify-release-manifest \
	release-manifest paper paper-tectonic clean

all: test verify-text verify-elementary verify-certificates

test:
	PYTHONPATH=src:tools $(PYTHON) -m unittest discover -s tests -v

verify-text:
	$(PYTHON) tools/check_repository_text.py

verify-elementary:
	mkdir -p $(BUILD)
	$(PYTHON) src/check_small_support.py > $(BUILD)/small-support.json
	cmp $(BUILD)/small-support.json evidence/small-support.json
	$(PYTHON) tools/verify_branch_coverage.py \
		--cycles 6 \
		--output $(BUILD)/branch-coverage.json \
		> $(BUILD)/branch-coverage.stdout.json
	cmp $(BUILD)/branch-coverage.json $(EVIDENCE)/branch-coverage.json

$(CNF_BUILD)/p3-c6-k%.cnf: src/orbit_cnf.py
	mkdir -p $(CNF_BUILD)
	$(PYTHON) src/orbit_cnf.py \
		--prime 3 \
		--cycles 6 \
		--degree-lower 18 \
		--degree-upper 24 \
		--root-adjacent-cycles $* \
		--output $@ \
		--metadata $(CNF_BUILD)/p3-c6-k$*.json \
		> $(CNF_BUILD)/p3-c6-k$*.generation.log

build-cnfs: $(CNFS)

regenerate-cnfs:
	rm -rf $(CNF_BUILD)
	$(MAKE) build-cnfs PYTHON="$(PYTHON)"

verify-cnfs: regenerate-cnfs
	cmp $(CNF_BUILD)/p3-c6-k0.json $(EVIDENCE)/p3-c6-k0.json
	cmp $(CNF_BUILD)/p3-c6-k1.json $(EVIDENCE)/p3-c6-k1.json
	cmp $(CNF_BUILD)/p3-c6-k2.json $(EVIDENCE)/p3-c6-k2.json
	cmp $(CNF_BUILD)/p3-c6-k3.json $(EVIDENCE)/p3-c6-k3.json
	$(PYTHON) tools/verify_branch_artifacts.py \
		$(CNF_BUILD) \
		--output $(CNF_BUILD)/cnf-audit.json \
		> $(CNF_BUILD)/cnf-audit.stdout.json
	cmp $(CNF_BUILD)/cnf-audit.json $(EVIDENCE)/cnf-audit.json

verify-certificates: verify-elementary verify-cnfs
	$(PYTHON) tools/verify_certificates.py \
		$(CNF_BUILD) \
		$(EVIDENCE) \
		--coverage $(EVIDENCE)/branch-coverage.json \
		--cnf-audit $(EVIDENCE)/cnf-audit.json \
		--expected-manifest $(EVIDENCE)/certificate-manifest.json \
		--output $(BUILD)/reconstructed-certificate-manifest.json \
		> $(BUILD)/reconstructed-certificate-manifest.stdout.json

verify-proofs: verify-certificates
	test -x "$(DRAT_TRIM)"
	test "$$(git -C "$(DRAT_TRIM_SOURCE)" rev-parse HEAD)" = \
		"$(DRAT_TRIM_COMMIT)"
	mkdir -p $(REPLAY_BUILD)
	$(PYTHON) tools/replay_proofs.py \
		$(CNF_BUILD) \
		$(EVIDENCE) \
		--checker "$(DRAT_TRIM)" \
		--checker-source-commit "$(DRAT_TRIM_COMMIT)" \
		--log-directory $(REPLAY_BUILD) \
		--output $(REPLAY_BUILD)/fresh-proof-replay.json \
		> $(REPLAY_BUILD)/fresh-proof-replay.stdout.json

paper:
	mkdir -p $(BUILD)/paper
	pdflatex -halt-on-error -output-directory=$(BUILD)/paper paper/main.tex
	pdflatex -halt-on-error -output-directory=$(BUILD)/paper paper/main.tex

paper-tectonic:
	test -n "$(TECTONIC)"
	mkdir -p $(BUILD)/paper
	$(TECTONIC) --outdir $(BUILD)/paper --keep-logs paper/main.tex

verify-release-manifest:
	$(PYTHON) tools/release_manifest.py --check

release-manifest:
	$(PYTHON) tools/release_manifest.py --write

clean:
	rm -rf $(BUILD)

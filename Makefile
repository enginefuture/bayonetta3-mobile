PY := .venv/bin/python
HOST := third_party/blade2-mobile/dm/host
.PHONY: setup analyze rewrite verify mac ios run test
setup:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt
analyze:
	$(PY) tools/analyze.py
rewrite:
	$(PY) tools/rewrite.py
verify:
	$(PY) tools/verify.py
mac:
	mkdir -p work
	$(MAKE) -C $(HOST) -f Makefile.bayonetta3
ios:
	$(PY) tools/build_ios.py
run:
	$(PY) tools/run_mac.py
test:
	$(PY) -m unittest discover -s tests -v
	mkdir -p work
	clang -Wall -Wextra -Wno-unused-function -o work/test-hle tests/test_hle.c
	./work/test-hle
	clang -Wall -Wextra -Ithird_party/blade2-mobile/dm/gfx/nvn/include -o work/test-nvn55 tests/test_nvn55.c
	./work/test-nvn55
	clang -Wall -Wextra -Ithird_party/blade2-mobile/dm/gfx/nvn/include -o work/test-nvn55-objects tests/test_nvn55_objects.c
	./work/test-nvn55-objects
	clang -Wall -Wextra -Ithird_party/blade2-mobile/dm/gfx/nvn/include -o work/test-descriptors tests/test_descriptors.c
	./work/test-descriptors
	clang -Wall -Wextra -Ithird_party/blade2-mobile/dm/gfx/nvn/include -o work/test-program-bind tests/test_program_bind.c
	./work/test-program-bind
	clang -Wall -Wextra -o work/test-fact-set tests/test_fact_set.c
	./work/test-fact-set
	clang -Wall -Wextra -Ithird_party/blade2-mobile/dm/gfx/nvn/include -o work/test-texels tests/test_texels.c third_party/blade2-mobile/dm/gfx/nvn/nvn_tex.c third_party/blade2-mobile/dm/gfx/tex/nvn_deswizzle.c
	./work/test-texels

.PHONY: shaders test-gpu public-check
public-check:
	python3 tools/audit_public.py --all-history
shaders:
	$(PY) tools/build_shaders.py
test-gpu:
	$(PY) tests/run_alpha.py
	$(PY) tests/run_depth_bounds.py
	$(PY) tests/run_indirect.py
	$(PY) tests/run_attachmentless.py
	$(PY) tests/run_gpu_profile.py
	$(PY) tests/run_indirect_batch.py

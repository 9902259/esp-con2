# All generated files remain outside the source directories.
.PHONY: build python web-build test firmware virtual-test web clean
build: python web-build
python:
	bash host/python/build.sh
web-build:
	cd host/javascript/example && npm ci && npm run build

test:
	build/venv/python/bin/python -m unittest discover -s host/python -p 'test_*.py'
	node --test host/javascript/api.test.mjs
firmware:
	python3.15 firmware/scripts/prepare_unified.py
	bash firmware/scripts/firmware.sh build
# Virtual diagnostics reuse the production UART transport without emulating BLE.
virtual-test:
	ESP_CON2_BOARD=sticky $(MAKE) firmware
	python3.15 firmware/scripts/test_virtual.py
# Serve the compiled example, including its sibling reusable API module.
web: web-build
	python3.15 -m http.server 8765 --bind 127.0.0.1 --directory build/js
clean:
	rm -rf build/host build/js build/firmware build/config build/cache

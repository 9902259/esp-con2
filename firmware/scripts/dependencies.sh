#!/usr/bin/env bash
set -euo pipefail
# Pin firmware dependencies so a fresh checkout uses the validated APIs.
cd "$(dirname "$0")/../.."
mkdir -p .deps
if [[ ! -d .deps/espp/.git ]]; then
  git clone --depth 1 --no-checkout https://github.com/esp-cpp/espp.git .deps/espp
fi
git -C .deps/espp fetch --depth 1 origin 351825c16377173ff9fd6716a0f089eaf461d7d2
git -C .deps/espp checkout 351825c16377173ff9fd6716a0f089eaf461d7d2
git -C .deps/espp submodule update --init --depth 1 \
  components/format/detail/fmt components/cli/detail/cli components/esp-nimble-cpp
if [[ ! -d .deps/esp-idf/.git ]]; then
  git clone --depth 1 --branch release/v6.1 --no-checkout https://github.com/espressif/esp-idf.git .deps/esp-idf
fi
git -C .deps/esp-idf fetch --depth 1 origin f0114250e205e33a945e2f3e7ec40085c5a029a2
git -C .deps/esp-idf checkout f0114250e205e33a945e2f3e7ec40085c5a029a2
git -C .deps/esp-idf submodule update --init --depth 1 --recursive
export IDF_TOOLS_PATH="$PWD/.deps/idf-tools"
# BLE-only firmware needs Xtensa, not the large RISC-V ULP or debugger toolchains.
# Use the same current stable Python as the host tooling.
"${ESP_CON2_IDF_PYTHON:-python3.15}" .deps/esp-idf/tools/idf_tools.py install xtensa-esp-elf
"${ESP_CON2_IDF_PYTHON:-python3.15}" .deps/esp-idf/tools/idf_tools.py install-python-env

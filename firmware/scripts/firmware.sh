#!/usr/bin/env bash
set -euo pipefail
# Reuse the project-local ESP-IDF installation for build, flash, or monitor.
cd "$(dirname "$0")/../.."
project_root="$PWD"
mkdir -p build/config build/logs
export IDF_TOOLS_PATH="$PWD/.deps/idf-tools"
# Select the installed IDF Python even when macOS defaults to another version.
if [[ -z "${IDF_PYTHON_ENV_PATH:-}" ]]; then
  candidates=("$IDF_TOOLS_PATH"/python_env/idf6.1_py*_env)
  if [[ ${#candidates[@]} -ne 1 || ! -x "${candidates[0]}/bin/python" ]]; then
    echo "Run firmware/scripts/dependencies.sh or set IDF_PYTHON_ENV_PATH" >&2
    exit 1
  fi
  export IDF_PYTHON_ENV_PATH="${candidates[0]}"
fi
export PATH="$IDF_PYTHON_ENV_PATH/bin:$PATH"
# The bootloader subprocess must also use our pinned local components.
export IDF_COMPONENT_MANAGER=0
# Let IDF export installed tools without requiring unused ULP/debugger packages.
export IDF_SKIP_TOOLS_CHECK=1
source .deps/esp-idf/export.sh >/dev/null
command -v xtensa-esp-elf-gcc >/dev/null || { echo "Run firmware/scripts/dependencies.sh first" >&2; exit 1; }
cd firmware
# Explicit caller overrides still work; otherwise keep generated files out of source folders.
defaults=()
has_build=false
has_config=false
for arg in "$@"; do
  [[ "$arg" == "-B" || "$arg" == --build-dir* ]] && has_build=true
  [[ "$arg" == SDKCONFIG=* ]] && has_config=true
done
$has_build || defaults+=(-B "$project_root/build/firmware/${ESP_CON2_PROFILE:-pro}")
$has_config || defaults+=(-D "SDKCONFIG=$project_root/build/config/sdkconfig-${ESP_CON2_PROFILE:-pro}")
exec idf.py "${defaults[@]}" "$@"

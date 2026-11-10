#!/usr/bin/env bash
set -euo pipefail
# Reuse the project-local ESP-IDF installation for build, flash, or monitor.
cd "$(dirname "$0")/../.."
project_root="$PWD"
# Keep Sticky's UART-only configuration separate from generic builds.
board="${ESP_CON2_BOARD:-generic}"
variant="${ESP_CON2_PROFILE:-pro}"
case "$board" in
  generic) ;;
  sticky) variant+="-sticky" ;;
  *) echo "Unknown ESP_CON2_BOARD: $board (use generic or sticky)" >&2; exit 1 ;;
esac
mkdir -p build/config build/logs
export IDF_TOOLS_PATH="$PWD/.deps/idf-tools"
# Select the current Python environment even if an older IDF environment remains.
if [[ -z "${IDF_PYTHON_ENV_PATH:-}" ]]; then
  python_version="$("${ESP_CON2_IDF_PYTHON:-python3.15}" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"
  export IDF_PYTHON_ENV_PATH="$IDF_TOOLS_PATH/python_env/idf6.1_py${python_version}_env"
  if [[ ! -x "$IDF_PYTHON_ENV_PATH/bin/python" ]]; then
    echo "Run firmware/scripts/dependencies.sh or set IDF_PYTHON_ENV_PATH" >&2
    exit 1
  fi
fi
export PATH="$IDF_PYTHON_ENV_PATH/bin:$PATH"
# The bootloader subprocess must also use our pinned local components.
export IDF_COMPONENT_MANAGER=0
# Let IDF export installed tools without requiring unused ULP/debugger packages.
export IDF_SKIP_TOOLS_CHECK=1
source .deps/esp-idf/export.sh >/dev/null
# Some UART bridges corrupt packets at IDF's 460800 default; -b/ESPBAUD still override.
export ESPBAUD="${ESPBAUD:-115200}"
command -v xtensa-esp-elf-gcc >/dev/null || { echo "Run firmware/scripts/dependencies.sh first" >&2; exit 1; }
cd firmware
# Explicit caller overrides still work; otherwise keep generated files out of source folders.
defaults=()
has_build=false
has_config=false
has_defaults=false
for arg in "$@"; do
  [[ "$arg" == "-B" || "$arg" == --build-dir* ]] && has_build=true
  [[ "$arg" == SDKCONFIG=* ]] && has_config=true
  [[ "$arg" == SDKCONFIG_DEFAULTS=* ]] && has_defaults=true
done
$has_build || defaults+=(-B "$project_root/build/firmware/$variant")
$has_config || defaults+=(-D "SDKCONFIG=$project_root/build/config/sdkconfig-$variant")
if ! $has_defaults; then
  sdk_defaults="sdkconfig.defaults"
  [[ "${ESP_CON2_PROFILE:-pro}" =~ ^(unified|joycon2-dual)$ ]] && sdk_defaults+=";sdkconfig.dual"
  [[ "$board" == sticky ]] && sdk_defaults+=";sdkconfig.sticky"
  defaults+=(-D "SDKCONFIG_DEFAULTS=$sdk_defaults")
fi
exec idf.py "${defaults[@]}" "$@"

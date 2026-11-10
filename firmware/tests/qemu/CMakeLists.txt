cmake_minimum_required(VERSION 3.20)
# Keep virtual diagnostics independent of the production BLE components and release images.
set(ENV{IDF_COMPONENT_MANAGER} "0")
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
set(COMPONENTS main esptool_py)
project(esp_con2_virtual)

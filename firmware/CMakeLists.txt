cmake_minimum_required(VERSION 3.20)
# Use the pinned local espp checkout, including its NimBLE submodule.
set(ENV{IDF_COMPONENT_MANAGER} "0")
include($ENV{IDF_PATH}/tools/cmake/project.cmake)
set(EXTRA_COMPONENT_DIRS "${CMAKE_CURRENT_LIST_DIR}/../.deps/espp/components")
# The S3 image includes both runtime controller modes. Other targets use the
# standalone Pro driver while their controller support is experimental.
if(IDF_TARGET STREQUAL "esp32s3")
  set(EXTRA_COMPONENT_DIRS
    "${CMAKE_CURRENT_LIST_DIR}/../.deps/joycon2-dual/switch2_pro"
    "${CMAKE_CURRENT_LIST_DIR}/../.deps/unified/unified_pro")
  foreach(component base_component logger format task timer nvs cli ble_gatt_server esp-nimble-cpp)
    list(APPEND EXTRA_COMPONENT_DIRS "${CMAKE_CURRENT_LIST_DIR}/../.deps/espp/components/${component}")
  endforeach()
  add_compile_definitions(ESP_CON2_UNIFIED=1 ESP_CON2_JOYCON2_DUAL=1)
endif()
set(COMPONENTS main esptool_py)
project(esp_con2)
if(IDF_TARGET STREQUAL "esp32s3")
  # Allow two controller identities to accept the same Switch central.
  target_link_options(esp_con2.elf PRIVATE "-Wl,--wrap=r_llm_is_dev_connected")
endif()

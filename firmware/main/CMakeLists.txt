# Link both serial drivers so USB-only and UART-bridge boards share one image.
# Only the combined profile links the isolated Pro implementation.
set(profile_requires "")
if("$ENV{ESP_CON2_PROFILE}" STREQUAL "unified")
  list(APPEND profile_requires unified_pro)
endif()
idf_component_register(SRCS "main.cpp" INCLUDE_DIRS "."
  REQUIRES switch2_pro nvs esp_driver_usb_serial_jtag esp_driver_uart esp_driver_gpio esp_timer esp_hw_support ${profile_requires})

# Compile the actual production serial transport against ESP-IDF's emulated drivers.
idf_component_register(SRCS "main.cpp" INCLUDE_DIRS "../../../main"
  REQUIRES esp_driver_uart esp_driver_gpio esp_driver_usb_serial_jtag nvs_flash)

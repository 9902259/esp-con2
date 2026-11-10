#pragma once

#include <cstring>
#include "sdkconfig.h"
#include "driver/usb_serial_jtag.h"
#include "driver/uart.h"
#include "driver/gpio.h"
#include "esp_err.h"

namespace serial_transport {
enum class Port { Usb, Uart };
constexpr Port ports[] = {Port::Usb, Port::Uart};

inline void init() {
#if !defined(CONFIG_ESP_CON2_SERIAL_UART)
#if defined(CONFIG_ESP_CONSOLE_USB_CDC)
#error "The USB-OTG console conflicts with native USB Serial/JTAG commands."
#endif
  // Native USB pins are fixed by the S3; no board peripherals are initialized.
  usb_serial_jtag_driver_config_t usb = {.tx_buffer_size = 2048, .rx_buffer_size = 2048};
  ESP_ERROR_CHECK(usb_serial_jtag_driver_install(&usb));
#endif
#if !defined(CONFIG_ESP_CON2_SERIAL_USB)
  // UART0 is shared with the ROM downloader and common onboard USB bridges.
  static_assert(GPIO_IS_VALID_OUTPUT_GPIO(CONFIG_ESP_CON2_UART_TX_PIN));
  static_assert(GPIO_IS_VALID_GPIO(CONFIG_ESP_CON2_UART_RX_PIN));
  static_assert(CONFIG_ESP_CON2_UART_TX_PIN != CONFIG_ESP_CON2_UART_RX_PIN);
#if defined(CONFIG_USJ_ENABLE_USB_SERIAL_JTAG)
  static_assert(CONFIG_ESP_CON2_UART_TX_PIN != 19 && CONFIG_ESP_CON2_UART_TX_PIN != 20);
  static_assert(CONFIG_ESP_CON2_UART_RX_PIN != 19 && CONFIG_ESP_CON2_UART_RX_PIN != 20);
#endif
  // Keep SDK logging off the command UART so writes have only one producer.
#if defined(CONFIG_ESP_CONSOLE_UART)
#error "Select USB Serial/JTAG or no SDK console when enabling the command UART."
#endif
  uart_config_t uart{};
  uart.baud_rate = 115200;
  uart.data_bits = UART_DATA_8_BITS;
  uart.parity = UART_PARITY_DISABLE;
  uart.stop_bits = UART_STOP_BITS_1;
  uart.flow_ctrl = UART_HW_FLOWCTRL_DISABLE;
  uart.source_clk = UART_SCLK_DEFAULT;
  ESP_ERROR_CHECK(uart_param_config(UART_NUM_0, &uart));
  ESP_ERROR_CHECK(uart_set_pin(UART_NUM_0, CONFIG_ESP_CON2_UART_TX_PIN,
                             CONFIG_ESP_CON2_UART_RX_PIN, UART_PIN_NO_CHANGE, UART_PIN_NO_CHANGE));
  ESP_ERROR_CHECK(uart_driver_install(UART_NUM_0, 2048, 2048, 0, nullptr, 0));
#endif
}

inline int read(Port port, char *data, size_t size) {
  // Poll both ports without delaying controller ticks or the input lease.
#if !defined(CONFIG_ESP_CON2_SERIAL_UART)
  if (port == Port::Usb) return usb_serial_jtag_read_bytes(data, size, 0);
#endif
#if !defined(CONFIG_ESP_CON2_SERIAL_USB)
  if (port == Port::Uart) return uart_read_bytes(UART_NUM_0, data, size, 0);
#endif
  return 0;
}

inline void reply(Port port, const char *message) {
  const auto size = std::strlen(message);
#if !defined(CONFIG_ESP_CON2_SERIAL_UART)
  if (port == Port::Usb) usb_serial_jtag_write_bytes(message, size, 0);
#endif
#if !defined(CONFIG_ESP_CON2_SERIAL_USB)
  if (port == Port::Uart) {
    // Reserve room for the whole reply; a stalled host must never block release.
    size_t available = 0;
    if (uart_get_tx_buffer_free_size(UART_NUM_0, &available) == ESP_OK && available >= size + 64)
      uart_write_bytes(UART_NUM_0, message, size);
  }
#endif
}
} // namespace serial_transport

// Package controller implements bounded, serialized commands to the ESP32-S3 board.
package controller

import (
	"context"
	"errors"
	"fmt"
	"io"
	"math"
	"strings"
	"sync"
	"time"

	"go.bug.st/serial"
	"go.bug.st/serial/enumerator"
)

var Buttons = strings.Fields("a b x y l r zl zr minus plus lstick rstick up down left right home capture gl gr c")

type Device struct {
	Port    string `json:"port"`
	Product string `json:"product"`
}

func Devices() ([]Device, error) {
	ports, err := enumerator.GetDetailedPortsList()
	if err != nil {
		return nil, err
	}
	devices := []Device{}
	for _, p := range ports {
		if p.IsUSB {
			devices = append(devices, Device{p.Name, p.Product})
		}
	}
	return devices, nil
}

type wire interface {
	io.ReadWriteCloser
	SetReadTimeout(time.Duration) error
	ResetInputBuffer() error
}

type Bridge struct {
	Port string
	mu   sync.Mutex
	open func(string) (wire, error)
	port wire
}

var errNotStreaming = errors.New("not streaming; pair/select the controller on Switch 2 first")

// Close releases the persistent serial connection when the server exits.
func (b *Bridge) Close() {
	b.mu.Lock()
	defer b.mu.Unlock()
	if b.port != nil {
		b.port.Close()
		b.port = nil
	}
}

func New(port string) *Bridge {
	return &Bridge{Port: port, open: func(name string) (wire, error) {
		return serial.Open(name, &serial.Mode{BaudRate: 115200,
			InitialStatusBits: &serial.ModemOutputBits{DTR: false, RTS: false}})
	}}
}

func Mask(names []string) (uint32, error) {
	var mask uint32
	for _, name := range names {
		found := false
		for bit, button := range Buttons {
			if strings.ToLower(name) == button {
				mask |= 1 << bit
				found = true
				break
			}
		}
		if !found {
			return 0, fmt.Errorf("unknown button %q; choose %s", name, strings.Join(Buttons, ", "))
		}
	}
	return mask, nil
}

func request(ctx context.Context, port wire, command string) (string, error) {
	if err := ctx.Err(); err != nil {
		return "", err
	}
	n, err := port.Write([]byte(command + "\n"))
	if err != nil {
		return "", err
	}
	if n != len(command)+1 {
		return "", io.ErrShortWrite
	}
	deadline := time.Now().Add(1500 * time.Millisecond)
	var line strings.Builder
	one := make([]byte, 1)
	for time.Now().Before(deadline) {
		if err := ctx.Err(); err != nil {
			return "", err
		}
		n, err := port.Read(one)
		if err != nil {
			return "", err
		}
		if n == 0 {
			continue
		}
		if one[0] != '\n' {
			if line.Len() >= 2048 {
				return "", errors.New("serial response too long")
			}
			line.WriteByte(one[0])
			continue
		}
		text := strings.TrimSpace(line.String())
		line.Reset()
		if strings.HasPrefix(text, "@ERR") {
			return "", errors.New(text)
		}
		if (command == "STATUS" && strings.HasPrefix(text, "@STATUS ")) || (command != "STATUS" && text == "@OK") {
			return text, nil
		}
	}
	return "", errors.New("ESP32-S3 board did not respond; check firmware and USB cable")
}

func (b *Bridge) withPort(ctx context.Context, action func(wire, string) (string, error)) (string, error) {
	// One operation owns the serial device for its entire press/release cycle.
	b.mu.Lock()
	defer b.mu.Unlock()
	if err := ctx.Err(); err != nil {
		return "", err
	}
	if b.port == nil {
		name := b.Port
		if name == "" {
			devices, err := Devices()
			if err != nil {
				return "", err
			}
			if len(devices) != 1 {
				return "", fmt.Errorf("found %d USB serial devices; specify --port", len(devices))
			}
			name = devices[0].Port
		}
		port, err := b.open(name)
		if err != nil {
			return "", err
		}
		if err := port.SetReadTimeout(100 * time.Millisecond); err != nil {
			port.Close()
			return "", err
		}
		if err := port.ResetInputBuffer(); err != nil {
			port.Close()
			return "", err
		}
		b.port = port
	}
	port := b.port
	status, err := request(ctx, port, "STATUS")
	if err != nil {
		port.Close()
		b.port = nil
		return "", err
	}
	// Require the board-neutral protocol identifier before sending input.
	if !strings.Contains(status, "device=esp-con2 protocol=1 ") {
		port.Close()
		b.port = nil
		return "", errors.New("unexpected device or firmware protocol")
	}
	result, err := action(port, status)
	if err != nil && !errors.Is(err, errNotStreaming) {
		port.Close()
		b.port = nil
	}
	return result, err
}

func (b *Bridge) Command(ctx context.Context, command string) (string, error) {
	switch command {
	case "STATUS", "RELEASE", "WAKE", "PAIR", "MODE pro", "MODE joycon":
	default:
		return "", errors.New("unsupported command")
	}
	result, err := b.withPort(ctx, func(port wire, status string) (string, error) {
		if command == "STATUS" {
			return status, nil
		}
		return request(ctx, port, command)
	})
	// A mode change reboots the device; reopen its serial transport on the next call.
	if strings.HasPrefix(command, "MODE ") {
		b.Close()
	}
	return result, err
}

func (b *Bridge) Input(ctx context.Context, names []string, axes [4]float64, milliseconds int) (string, error) {
	mask, err := Mask(names)
	if err != nil {
		return "", err
	}
	if milliseconds < 20 || milliseconds > 10000 {
		return "", errors.New("duration_ms must be 20–10000")
	}
	for _, v := range axes {
		if math.IsNaN(v) || math.IsInf(v, 0) || v < -1 || v > 1 {
			return "", errors.New("axes must be finite values in [-1, 1]")
		}
	}
	return b.withPort(ctx, func(port wire, status string) (result string, err error) {
		if !strings.Contains(status, "streaming=1") {
			return "", errNotStreaming
		}
		// Cancellation still gets a best-effort release; the firmware also has a 500 ms lease.
		defer func() {
			releaseCtx, cancel := context.WithTimeout(context.Background(), 1600*time.Millisecond)
			defer cancel()
			_, releaseErr := request(releaseCtx, port, "RELEASE")
			if err == nil && releaseErr != nil {
				err = fmt.Errorf("release failed (watchdog will release): %w", releaseErr)
			}
		}()
		command := fmt.Sprintf("STATE %x %.6f %.6f %.6f %.6f", mask, axes[0], axes[1], axes[2], axes[3])
		deadline := time.Now().Add(time.Duration(milliseconds) * time.Millisecond)
		for {
			if _, err = request(ctx, port, command); err != nil {
				return "", err
			}
			remaining := time.Until(deadline)
			if remaining <= 0 {
				return "Input completed and released", nil
			}
			if remaining > 100*time.Millisecond {
				remaining = 100 * time.Millisecond
			}
			timer := time.NewTimer(remaining)
			select {
			case <-ctx.Done():
				timer.Stop()
				return "", ctx.Err()
			case <-timer.C:
			}
			if time.Now().After(deadline) {
				return "Input completed and released", nil
			}
		}
	})
}

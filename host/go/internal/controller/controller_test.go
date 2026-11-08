package controller

import (
	"context"
	"errors"
	"io"
	"math"
	"strings"
	"testing"
	"time"
)

// The fake responds like firmware without sending any input to a real console.
type fakePort struct {
	response  []byte
	writes    []string
	status    string
	failState bool
	cancel    context.CancelFunc
	closed    bool
}

func (f *fakePort) Write(p []byte) (int, error) {
	command := strings.TrimSpace(string(p))
	f.writes = append(f.writes, command)
	response := "@OK\n"
	if command == "STATUS" {
		response = f.status + "\n"
	}
	if strings.HasPrefix(command, "STATE") {
		if f.cancel != nil {
			f.cancel()
		}
		if f.failState {
			return 0, errors.New("USB disconnected")
		}
	}
	f.response = append(f.response, []byte(response)...)
	return len(p), nil
}
func (f *fakePort) Read(p []byte) (int, error) {
	if len(f.response) == 0 {
		return 0, io.EOF
	}
	n := copy(p, f.response)
	f.response = f.response[n:]
	return n, nil
}
func (f *fakePort) Close() error                       { f.closed = true; return nil }
func (f *fakePort) SetReadTimeout(time.Duration) error { return nil }
func (f *fakePort) ResetInputBuffer() error            { f.response = nil; return nil }
func bridgeFor(f *fakePort) *Bridge {
	return &Bridge{Port: "fake", open: func(string) (wire, error) { return f, nil }}
}

const connected = "@STATUS device=esp-con2 protocol=1 paired=1 connected=1 streaming=1"

func TestInputAlwaysReleases(t *testing.T) {
	for _, mode := range []string{"success", "cancel", "disconnect"} {
		t.Run(mode, func(t *testing.T) {
			ctx, cancel := context.WithCancel(context.Background())
			defer cancel()
			f := &fakePort{status: connected, failState: mode == "disconnect"}
			if mode == "cancel" {
				f.cancel = cancel
			}
			b := bridgeFor(f)
			_, err := b.Input(ctx, []string{"a", "l"}, [4]float64{}, 20)
			if (err != nil) != (mode != "success") {
				t.Fatalf("unexpected result: %v", err)
			}
			if f.writes[len(f.writes)-1] != "RELEASE" {
				t.Fatalf("not released: %v", f.writes)
			}
			b.Close()
			if !f.closed {
				t.Fatal("port not closed on shutdown")
			}
		})
	}
}

func TestSerialPortIsReused(t *testing.T) {
	f := &fakePort{status: connected}
	opens := 0
	b := &Bridge{Port: "fake", open: func(string) (wire, error) { opens++; return f, nil }}
	defer b.Close()
	for i := 0; i < 2; i++ {
		if _, err := b.Command(context.Background(), "STATUS"); err != nil {
			t.Fatal(err)
		}
	}
	if opens != 1 || f.closed {
		t.Fatalf("port reopened or closed: opens=%d", opens)
	}
}

func TestRejectsInvalidInputBeforeOpening(t *testing.T) {
	b := &Bridge{open: func(string) (wire, error) { t.Fatal("opened hardware for invalid input"); return nil, nil }}
	for _, test := range []struct {
		names []string
		axes  [4]float64
		ms    int
	}{
		{[]string{"invalid"}, [4]float64{}, 100},
		{nil, [4]float64{math.NaN()}, 100},
		{nil, [4]float64{2}, 100},
		{nil, [4]float64{}, 10001},
	} {
		if _, err := b.Input(context.Background(), test.names, test.axes, test.ms); err == nil {
			t.Fatal("accepted invalid input")
		}
	}
}

func TestRefusesWrongDeviceOrInactiveStream(t *testing.T) {
	for _, status := range []string{"@STATUS something-else", strings.Replace(connected, "streaming=1", "streaming=0", 1)} {
		f := &fakePort{status: status}
		if _, err := bridgeFor(f).Input(context.Background(), []string{"a"}, [4]float64{}, 20); err == nil {
			t.Fatal("accepted unavailable controller")
		}
		if len(f.writes) != 1 || f.writes[0] != "STATUS" {
			t.Fatalf("unexpected input: %v", f.writes)
		}
	}
}

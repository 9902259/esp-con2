package main

import (
	"errors"
	"flag"
	"testing"
)

func TestCommandValidation(t *testing.T) {
	// Dispatch must reject malformed commands before opening any serial device.
	for _, args := range [][]string{nil, {"unknown"}, {"mcp", "unexpected"}, {"mode", "invalid"}, {"stick", "left"}} {
		if err := run(args); err == nil {
			t.Fatalf("accepted invalid command: %v", args)
		}
	}
	for _, args := range [][]string{{"--help"}, {"mcp", "--help"}} {
		if err := run(args); !errors.Is(err, flag.ErrHelp) {
			t.Fatalf("help %v: %v", args, err)
		}
	}
}

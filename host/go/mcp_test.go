package main

import (
	"context"
	"testing"
	"time"

	"esp-con2/internal/controller"
	"github.com/modelcontextprotocol/go-sdk/mcp"
)

func TestMCPDiscoveryAndValidation(t *testing.T) {
	// Exercise the actual SDK session, including schemas and tool-error responses.
	ctx, cancel := context.WithTimeout(context.Background(), 5*time.Second)
	defer cancel()
	st, ct := mcp.NewInMemoryTransports()
	ss, err := newServer(controller.New("/does/not/exist")).Connect(ctx, st, nil)
	if err != nil {
		t.Fatal(err)
	}
	defer ss.Close()
	client := mcp.NewClient(&mcp.Implementation{Name: "test", Version: "1"}, nil)
	cs, err := client.Connect(ctx, ct, nil)
	if err != nil {
		t.Fatal(err)
	}
	defer cs.Close()
	listed, err := cs.ListTools(ctx, nil)
	if err != nil {
		t.Fatal(err)
	}
	if len(listed.Tools) != 6 {
		t.Fatalf("got %d tools", len(listed.Tools))
	}
	for _, args := range []map[string]any{
		{"buttons": []string{"not-a-button"}},
		{"duration_ms": 10001},
		{"lx": 2},
	} {
		result, err := cs.CallTool(ctx, &mcp.CallToolParams{Name: "controller_input", Arguments: args})
		if err != nil {
			t.Fatal(err)
		}
		if !result.IsError {
			t.Fatalf("invalid input succeeded: %v", args)
		}
	}
	result, err := cs.CallTool(ctx, &mcp.CallToolParams{Name: "controller_status", Arguments: map[string]any{}})
	if err != nil {
		t.Fatal(err)
	}
	if !result.IsError {
		t.Fatal("missing hardware reported success")
	}
}

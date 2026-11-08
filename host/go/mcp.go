// MCP tools share the same serial bridge as the manual CLI.
package main

import (
	"context"
	"log"
	"os"
	"os/signal"
	"syscall"

	"esp-con2/internal/controller"
	"github.com/modelcontextprotocol/go-sdk/mcp"
)

type empty struct{}
type message struct {
	Message string `json:"message"`
}
type devices struct {
	Devices []controller.Device `json:"devices"`
}
type input struct {
	Buttons    []string `json:"buttons,omitempty" jsonschema:"Buttons to hold together: a b x y l r zl zr minus plus lstick rstick up down left right home capture gl gr c"`
	LX         float64  `json:"lx,omitempty" jsonschema:"Left stick X from -1 to 1"`
	LY         float64  `json:"ly,omitempty" jsonschema:"Left stick Y from -1 to 1"`
	RX         float64  `json:"rx,omitempty" jsonschema:"Right stick X from -1 to 1"`
	RY         float64  `json:"ry,omitempty" jsonschema:"Right stick Y from -1 to 1"`
	DurationMS int      `json:"duration_ms,omitempty" jsonschema:"Hold duration 20 to 10000 milliseconds; omitted or zero defaults to 120"`
}

func newServer(bridge *controller.Bridge) *mcp.Server {
	server := mcp.NewServer(&mcp.Implementation{Name: "esp-con2", Version: "0.1.0"}, nil)
	mcp.AddTool(server, &mcp.Tool{Name: "list_devices", Description: "List USB serial ports on this Mac; does not connect or press buttons.", Annotations: &mcp.ToolAnnotations{ReadOnlyHint: true}},
		func(ctx context.Context, req *mcp.CallToolRequest, in empty) (*mcp.CallToolResult, devices, error) {
			ports, err := controller.Devices()
			return nil, devices{ports}, err
		})
	for name, spec := range map[string]struct{ command, description string }{
		"controller_status": {"STATUS", "Read emulator pairing, connection, and input-streaming status. Does not provide a screenshot or game state."},
		"release_controls":  {"RELEASE", "Release all buttons and center both sticks."},
		"wake_console":      {"WAKE", "Ask the previously paired Switch 2 to wake; requires a stored bond and no current BLE connection."},
		"reset_pairing":     {"PAIR", "Forget the emulator's saved console bond to pair again. Use only when the user requests pairing/resetting; open the console pairing screen first."},
	} {
		mcp.AddTool(server, &mcp.Tool{Name: name, Description: spec.description, Annotations: &mcp.ToolAnnotations{ReadOnlyHint: name == "controller_status"}},
			func(ctx context.Context, req *mcp.CallToolRequest, in empty) (*mcp.CallToolResult, message, error) {
				text, err := bridge.Command(ctx, spec.command)
				return nil, message{text}, err
			})
	}
	mcp.AddTool(server, &mcp.Tool{Name: "controller_input", Description: "Hold buttons and/or sticks for a bounded duration, then release everything. Requires streaming=1. Input only: cannot observe the game or confirm an in-game outcome."},
		func(ctx context.Context, req *mcp.CallToolRequest, in input) (*mcp.CallToolResult, message, error) {
			if in.DurationMS == 0 {
				in.DurationMS = 120
			}
			text, err := bridge.Input(ctx, in.Buttons, [4]float64{in.LX, in.LY, in.RX, in.RY}, in.DurationMS)
			return nil, message{text}, err
		})
	return server
}

func runMCP(port string) error {
	// Keep stdout exclusively for MCP JSON-RPC messages.
	log.SetOutput(os.Stderr)
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	bridge := controller.New(port)
	defer bridge.Close()
	err := newServer(bridge).Run(ctx, &mcp.StdioTransport{})
	if ctx.Err() != nil {
		return nil
	}
	return err
}

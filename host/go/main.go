// esp-con2 provides CLI commands and an MCP server in one executable.
package main

import (
	"context"
	"errors"
	"esp-con2/internal/controller"
	"flag"
	"fmt"
	"os"
	"os/signal"
	"strconv"
	"strings"
	"syscall"
)

func run(arguments []string) error {
	// Accept MCP options after its subcommand as well as ordinary leading flags.
	mcpMode := len(arguments) > 0 && arguments[0] == "mcp"
	if mcpMode {
		arguments = arguments[1:]
	}
	flags := flag.NewFlagSet("esp-con2", flag.ContinueOnError)
	port := flags.String("port", os.Getenv("ESP_CON2_PORT"), "USB serial port")
	seconds := flags.Float64("seconds", .1, "input duration, 0.02–10 seconds")
	flags.Usage = func() {
		fmt.Fprintln(flags.Output(), "usage: esp-con2 [options] ports|status|release|wake|pair|mode pro|mode joycon|tap a|hold l+r|stick left X Y")
		fmt.Fprintln(flags.Output(), "       esp-con2 mcp [--port PORT]")
		flags.PrintDefaults()
	}
	if err := flags.Parse(arguments); err != nil {
		return err
	}
	args := flags.Args()
	if mcpMode {
		if len(args) != 0 {
			return fmt.Errorf("unexpected MCP arguments: %v", args)
		}
	} else if len(args) == 1 && args[0] == "mcp" {
		mcpMode = true
	} else if len(args) == 0 {
		flags.Usage()
		return fmt.Errorf("specify a command")
	}
	if mcpMode {
		return runMCP(*port)
	}
	if args[0] == "ports" {
		ports, err := controller.Devices()
		for _, p := range ports {
			fmt.Println(p.Port, p.Product)
		}
		return err
	}
	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	bridge := controller.New(*port)
	defer bridge.Close()
	var result string
	var err error
	switch args[0] {
	case "status", "release", "wake", "pair":
		result, err = bridge.Command(ctx, strings.ToUpper(args[0]))
	case "mode":
		if len(args) != 2 || (args[1] != "pro" && args[1] != "joycon") {
			return fmt.Errorf("mode must be pro or joycon")
		}
		result, err = bridge.Command(ctx, "MODE "+args[1])
	case "tap", "hold":
		if len(args) != 2 {
			return fmt.Errorf("specify buttons, e.g. l+r")
		}
		result, err = bridge.Input(ctx, strings.Split(args[1], "+"), [4]float64{}, int(*seconds*1000))
	case "stick":
		if len(args) != 4 || (args[1] != "left" && args[1] != "right") {
			return fmt.Errorf("stick left|right X Y")
		}
		var axes [4]float64
		offset := 0
		if args[1] == "right" {
			offset = 2
		}
		for i := 0; i < 2; i++ {
			v, e := strconv.ParseFloat(args[2+i], 64)
			if e != nil {
				return e
			}
			axes[offset+i] = v
		}
		result, err = bridge.Input(ctx, nil, axes, int(*seconds*1000))
	default:
		return fmt.Errorf("unknown command %q", args[0])
	}
	if err == nil {
		fmt.Println(result)
	}
	return err
}
func main() {
	if err := run(os.Args[1:]); err != nil && !errors.Is(err, flag.ErrHelp) {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
}

@echo off
REM Call this script to compile the `adder.zig` source into a platform-agnostic `adder.wasm` module
zig build-exe adder.zig -target wasm32-freestanding -fno-entry --export=add

"""
Basic invocation of a zig-build WASM module
"""

import wasmtime

def main():
    """
    Uses wasmtime to load the adder module, then print the results of a basic
    call to that module.
    """
    store = wasmtime.Store()
    module = wasmtime.Module.from_file(store.engine, "./adder.wasm")
    instance = wasmtime.Instance(store, module, [])
    add = instance.exports(store)["add"]
    print("add(2, 3) = %d" % add(store, 2, 3))

if __name__ == "__main__":
    main()

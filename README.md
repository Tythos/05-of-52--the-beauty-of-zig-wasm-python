If you're poked around a few things, you know that WASM can be pretty neat. That having said, it still feels stuck in a niche, only realizing a fraction of its full potential. Consider:

* If you're not writing in a language specifically set up to enable WASM generation, like Rust, you're likely going to require onerous third-party tooling (I'm looking at you, emscripten!) with significant "adapter" layers on *both* sides of your code

* The web-based applications can be interesting but the relative lack of transparency (compared to, for example, Web Workers or other ways to expand concurrent computing within a web application) of developer tools raises the barrier to adoption in the community it was originally targeting

* Interoperability is limited by the binary data interface, with little standard representation for common data structures like strings, hash maps, and arrays. To say nothing of working through memory buffers (whether runtime allocation is required or not).

So. Where are we to go?

## Enter the Zigman

Have you messed with Zig?

https://www.youtube.com/watch?v=kxT8-C1vmd4

It's common considered to be a C successor oriented around systems programming. But, unlike Rust, it's streamlined enough to be a much lower barrier for adoption into general-purpose programming, even though it comes with a lot of the more powerful modern language features like optionals and error types.

I think of it like Rust, but without fighting against the borrow checker. Instead of using a tool that tries to *aggrivate* you, you're using a tool that tries to *help* you.

But one of the things that really makes it shine is how suitable it is for targeting WASM. The Zig compiler is, out of the box, very well suited (by design) for targeting a wide variety of architectures ("build to anywhere, from anywhere" is a big priority), including WASM. (We'll see if that survives the LLVM divorce!)

Apparently, I'm not the only one thinking these thoughts:

https://blog.battlefy.com/zig-and-webassembly-are-a-match-made-in-heaven

Of course, memory allocation is one place where WASM and Zig go really well together, but even beyond that, there's outstanding synergy in the primitive type systems and struct packing that make data management in general a lot more transparent than, I would say, the majority of other languages you might try to write a WASM build in.

## But How Do We Use It?

I think one of the major obstacles to WASM adoption isn't necessarily how to *write* something that builds to WASM, but rather how to *use* it. If you don't have a self-contained application, there's significant limitations on the interoperability with other modules and with the calling environment in general. At best, on the browser Javascript side, you might combine web workers with a minimal WASM call interface to set up something like "WebThreads":

https://github.com/Tythos/WebThreads

But in general, there are no theoretical constraints on what *could* consume a WASM module. After all, it's effectively just a set of instructions for a stack machine. So, any language that implements an interface to that stack machine could support calls into the module at runtime.

That's one reason why, in general, I think the WASM-as-dynamic-library approach is so interesting, and something I'll probably come back to in the future. We're going to consider one particular usecase I think ends up being pretty interesting: Writing WASM modules in Zig to be consumed (called) by a runtime in Python. I think you'll agree that this is a pretty interesting alternative to traditional CFFI/ABI, and in my opinion this is a lot closer to the core of what WASM could be in the future.

## Generating WASM in Zig

Let's put together a basic WASM module in Zig. Here's the classic example; save it to `adder.zig`.

```zig
pub export fn add(a: i32, b: i32) i32 {
    return a + b;
}
```

We can build this to a WASM module with some specific command-line invocation. It's possible to automate some of this in your `build.zig` file but for simplicity's sake we'll just call it like so:

```sh
zig build-exe adder.zig -target wasm32-freestanding -fno-entry --export=add
```

This minimal build call, ironically, is considerably more complicated than the program itself. Let's break it down. (While I'm at it, I should mention that I'm following the Mach nomination release cycle, which is currently focused on `0.12.0-dev.2063`.)

* `build-exe` is a specific build command--though we're not building an executable, the same call with `build-lib` will *NOT* result in a WASM module

* `adder.zig` in this case is our source file; replace this with whatever file you saved our example to

* `-target wasm32-freestanding` indicates to the Zig compiler that we will built to the 32-bit WASM architecture, whereas "freestanding" indicates this is not specific to a particular operating system; you can look at the output of `zig targets` yourself (or pipe it to a JSON file--it's quite lengthy)

* `-fno-entry` is required to indicate (given that we invoked `build-exe`) that there is no entry point

* `--export=add` tells the compiler what specific symbols need to be exposed by name for external invocation

So what does that create? By default, this should generate an `adder.wasm` module. But does it work? Let's find out.

## WASM in Python

There are several options for "consuming" WASM in Python. We'll focus on one in particular--"wasmtime". Assuming you have a Python environment already installed, go ahead and `pip install wasmtime`. Then, we're ready to write our invocation.

```py
import wasmtime

def main():
    store = wasmtime.Store()
```

The first ingredient we need is a "store". This is a representation of a memory buffer that can be utilized within the WASM runtime once we instantiate the module.

```py
    module = wasmtime.Module.from_file(store.engine, "./adder.wasm")
```

Next, we need to create the module from our WASM file. The engine manages the runtime and its mappings to the memory buffer ("store").

```py
    instance = wasmtime.Instance(store, module, [])
```

If you've used WASM in the Javascript ecosystem, you're probably familiar with the need to instantiate a WASM module once you've parsed the instructions. In this case, that instantiation also comes with the bindings into the store needed at runtime.

```py
    add = instance.exports(store)["add"]
```

Within the space defined by our module instance, we can now identify the specific symbol for invocation. This is done by string mapping against the name of the function we know we want to call.

```py
    print("add(2, 3) = %d" % add(store, 2, 3))
```

Now we're ready to invoke the function! Don't ask me why we still need to pass a store that was already bound to the instnace *and* passed to the exports retrival.

```py

if __name__ == "__main__":
    main()
```

Lastly, we close the module with a default call to `main()` for command-line invocation. Now let's save that script to `main.py` and try calling it from the command line:

```sh
> python main.py
add(2, 3) = 5
```

## Next Steps

Okay, this is pretty cool. We even did most of it in Windows! But is it usable?

There are several complications and drawbacks we'd want to address, mostly related to how more complex data structures are handled.

For example, we would want strings and structs (and even structs *with* strings! gasp!) to be supported if we want to scale out the implementation of a data-intensive interface. This would be particularly critical to support structures like hash maps.

This isn't easy. There are several obstacles:

* Structs would need to be exposed by some kind of a "factory" function that can be used to instantiate the specific format of a struct

* Structs would need to be "packed" in compliance with the C ABI (or externally defined)

* Strings would need specific in-memory representation, though there are ways around this

* String fields in structs... don't get me started here, it's possible within Zig itself of course but translating this to something that doesn't make Zig panic about the calling convention is an unsolved mystery thus far

Why would we care, though?

## WASM as a Dynamic Library

Ultimately, Python was an arbitrary example here. What we're really looking to do is, use WASM as a modernized vision of the "dynamic libary" that doesn't lose itself to DLL hell and binary obfuscation. Given a platform-neutral set of instructions, there's no reason *any* language with a functional WASM runtime shouldn't be able to share and consume such a library.

If this is possible, then Zig (or any other WASM generator) code can be shared and invoked by a wide array of languages. There's a lot of lower-level software tools, beyond just systems programming, that would benefit considerably from a universal implementation in a stack intermediary. Numerical methods, integrators, tensor math, scientific / physics modeling, concurrent simulation...

You could, theoretically, even implement an ECS-style engine in which each subsystem is defined by it's own self-contained WASM module, running against a specific memory space with known mappings to component data structures. That would be neat. As someone who works mostly in modeling & simulation, the idea of writing *one* set of algorithms for things like flight controllers is very exciting.

To do this, though, you'd need to address the obstacles itemized in the previous section. This would be particularly important for complex numeric types like n-dimensional tensors:

https://github.com/andrewCodeDev/ZEIN

In short, the Zig+WASM combination has me excited in a way I haven't felt about new programming language developments since WebGL, and (before that) the advent of a standardized Python. But of course it's not even specific to Zig--any other language with the right supports could both generate and consume such libaries (though let's be honest, some of the options are better than others). Python was the example we went with because it opens consumption of Zig tools to a whole universe of developers working within a very popular paradigm that is both compatible with this use case and missing a lot of the better features of Zig itself.

But we've still got some non-zero ways to go until that dream is within reach. We'll keep working on it.

## Appendix: Making It Work

If you're cloning this from a fresh repo, here are some basic steps:

1. Run the `build.bat` file (or copy-paste its single build instruction, if you're not on Windows); this should generate an `adder.wasm` file

2. Install the Python requirements (`pip install -r requirements.txt`)

3. Run the main Python script (`python main.py`)

You should see the example output (`add(2, 3) = 5`) upon successful execution.

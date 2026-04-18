## GCC M68K Assembler Optimizer

Pattern matching peephole optimizer, static data flow analysis for registers liveness, branch instruction size reduction, 
use word size on address to exploit address register sign extension, and many more optimizations.

Only useful for the [SGDK](https://github.com/Stephane-D/SGDK) framework, which builds a m68k elf artifact prior 
to the final binary rom artifact.

This script is intended to be executed with gcc plugin feature at `PLUGIN_FINISH` phase, which is 
the last opportunity we have to access assembly code before exiting gcc and start the linking phase.

At `PLUGIN_FINISH` phase we can access the m68k assembly code generated from all the **.c units** in our project 
and those by the **SGDK** library, including the inline asm blocks. Assembly **.s, .S, .asm units** are excluded from this phase.

The optimizer depends heavily on the project you run it. On some, it saves 1% of CPU per frame 
(approximately 2 scanlines), which is a sign that the project's hot path might be better rewritten in asm (if not already).

See [optimize_lst.py](optimize_lst.py "optimize_lst.py") at header section for a list of reference web sites where I took the peepholes, 
and all the switches the optimizer provides for more cycles squishing.

These are five of my projects for which I use the optimizer as a test base.
The next picture outlines how many optimization patterns were applied on each of them.

![stats.jpg](stats.png?raw=true "stats.png")

### Sources

https://gist.github.com/flamewing/ad17bf22875be36ad4ae26f159a94f8b  
http://www.easy68k.com/paulrsm/doc/asp68k6.txt  
https://mikro.naprvyraz.sk/docs/Optimize/68OPT.TXT  
http://preserve.mactech.com/articles/mactech/Vol.08/08.02/Efficient68000/index.html  
http://www.easy68k.com/paulrsm/doc/trick68k.htm  
https://wiki.neogeodev.org/index.php?title=Optimization  
http://www.ibaug.de/vasm/doc/vasm.pdf  
http://www.csua.berkeley.edu/~muchandr/m68k  
https://github.com/Samuel-DEVULDER/popt  
Custom patterns found from gcc -S outputs  

### Build gcc and the plugin

First, build gcc m68k toolchain with plugin support enabled. This is straight forward on Linux systems, 
even on WSL (Windows Subsytem for Linux), but impossible on Windows systems (I couldn't build it yet).  
Use script [build_gcc.sh](build_gcc.sh "build_gcc.sh") (or [build_gcc_mingw64_windows.sh](build_gcc_mingw64_windows.sh "build_gcc_mingw64_windows.sh") **WIP**).  
Add the toolchain into your PATH so SGDK can see it, and also to correctly build the plugin in next step.

Then, compile the gcc plugin `optimizer_plugin.c` responsible to execute the python script over the 
gcc m68k assembly code. See script [build_plugin.sh](build_plugin.sh "build_plugin.sh") 
(or [build_plugin_mingw64_windows.sh](build_plugin_mingw64_windows.sh "build_plugin_mingw64_windows.sh") **WIP**).  
This will create `optimizer_plugin.so`/`optimizer_plugin.dll` file. Move it into SGDK's `tools` folder.  
Move `optimize_lst.py` and `optimize_mul_patterns.py` files into SGDK's `tools` folder.

Optionally, build SGDK. You can use script [build_sgdk.sh](build_sgdk.sh "build_sgdk.sh").  
This step is not required if you have your SGDK already built/installed. Then you can rely SGDK's `makefile.gen` will take 
the new *m68k-elf-* binaries added to the PATH in previous step.

### Execution
- Open SGDK's `makefile.gen`:
  - Add next lines somewhere after the definition of **OUT_DIR** variable:  
    ```
	PLUGIN_PEEPHOLES_PARAMS := -fplugin=$(GDK)/tools/optimizer_plugin.so -fplugin-arg-optimizer_plugin-disable=0 -fplugin-arg-optimizer_plugin-keep-files=0
	PLUGIN_SYMBOLS_OPTIMIZED_PARAMS := $(PLUGIN_PEEPHOLES_PARAMS) -fplugin-arg-optimizer_plugin-symbols-opt-path=$(OUT_DIR)/symbol_opt.txt
	PLUGIN_SYMBOLS_CANONICAL_OPTIMIZED_PARAMS := $(PLUGIN_SYMBOLS_OPTIMIZED_PARAMS) -fplugin-arg-optimizer_plugin-symbols-canonical-path=$(OUT_DIR)/symbol_canonical.txt
	```
  - Replace the rule for `$(OUT_DIR)/rom.out` as next:  
    ```
	ifneq ($(PLUGIN_PEEPHOLES_PARAMS),)
    $(OUT_DIR)/rom.out: $(OUT_DIR)/sega.o $(OUT_DIR)/cmd_ $(LIBMD)
		@$(MKDIR) -p $(dir $@)
		@$(RM) -f $(OUT_DIR)/symbol_opt.txt
		@$(RM) -f $(OUT_DIR)/symbol_canonical.txt
		$(CC) $(PLUGIN_PEEPHOLES_PARAMS) -m68000 -B$(BIN) -n -T $(GDK)/md.ld -nostdlib $(OUT_DIR)/sega.o @$(OUT_DIR)/cmd_ $(LIBMD) $(LIBGCC) -o $(OUT_DIR)/rom.out -Wl,--gc-sections -flto -flto=auto -ffat-lto-objects
		$(NM) $(LTO_PLUGIN) -n -l $(OUT_DIR)/rom.out > $(OUT_DIR)/symbol_opt.txt
		$(CC) $(PLUGIN_SYMBOLS_OPTIMIZED_PARAMS) -m68000 -B$(BIN) -n -T $(GDK)/md.ld -nostdlib $(OUT_DIR)/sega.o @$(OUT_DIR)/cmd_ $(LIBMD) $(LIBGCC) -o $(OUT_DIR)/rom.out -Wl,--gc-sections -flto -flto=auto -ffat-lto-objects
		$(NM) $(LTO_PLUGIN) -n -l $(OUT_DIR)/rom.out > $(OUT_DIR)/symbol_canonical.txt
		$(CC) $(PLUGIN_SYMBOLS_CANONICAL_OPTIMIZED_PARAMS) -m68000 -B$(BIN) -n -T $(GDK)/md.ld -nostdlib $(OUT_DIR)/sega.o @$(OUT_DIR)/cmd_ $(LIBMD) $(LIBGCC) -o $(OUT_DIR)/rom.out -Wl,--gc-sections -flto -flto=auto -ffat-lto-objects
		@$(RM) -f $(OUT_DIR)/symbol_opt.txt
		@$(RM) -f $(OUT_DIR)/symbol_canonical.txt
		@$(RM) $(OUT_DIR)/cmd_
    else
    $(OUT_DIR)/rom.out: $(OUT_DIR)/sega.o $(OUT_DIR)/cmd_ $(LIBMD)
    	@$(MKDIR) -p $(dir $@)
    	$(CC) -m68000 -B$(BIN) -n -T $(GDK)/md.ld -nostdlib $(OUT_DIR)/sega.o @$(OUT_DIR)/cmd_ $(LIBMD) $(LIBGCC) -o $(OUT_DIR)/rom.out -Wl,--gc-sections -flto -flto=auto -ffat-lto-objects
    	@$(RM) $(OUT_DIR)/cmd_
    endif
    ```
- Make sure python 3.10+ is in your PATH.
- Build your project:
  - `make -f $GDK/makefile.gen release -j1`

You can find me in the SGDK Discord server: https://discord.gg/xmnBWQS

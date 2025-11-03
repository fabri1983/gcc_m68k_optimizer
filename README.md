## GCC M68K Assembler Optimizer

Only useful for the [SGDK](https://github.com/Stephane-D/SGDK) framework, which builds m68k elf artifacts prior 
to the final binary rom artifact.

This solution is intended to be executed with gcc plugin feature at `PLUGIN_FINISH` phase, which is 
the last opportunity we have to access assembly code before exiting gcc and start the linking phase.

At `PLUGIN_FINISH` phase we can access all the m68k assembly code generated from all the .c units in our project and 
the SGDK library, including the inline asm blocks.

The optimization depends heavily on the project you run it over. On some of them it saves 1% of CPU per frame 
(approximately 2 scanlines), which is a sign that the project's hot path might be better rewritten in asm (if not already).

See [optimize_lst.py](optimize_lst.py "optimize_lst.py") at header section for a list of all peepholes and switches 
the optimizer provides.

### Build gcc and the plugin

First you need to build your gcc toolchain with plugin support enabled. This is straight forward on Linux systems, 
even on WSL (Windows Subsytem for Linux), but impossible on Windows systems (I couldn't build it yet).  
Add the toolchain into your PATH (or copy it into SGDK's `bin` folder) so SGDK can see it.

Then you need to compile the gcc plugin `optimizer_plugin.c`, responsible to execute the python script 
over the gcc m68k assembly code. See script [build_plugin.sh](build_plugin.sh "build_plugin.sh") 
(or [build_plugin_w64.sh](build_plugin_w64.sh "build_plugin_w64.sh")).  
This will create `optimizer_plugin.so` (or `optimizer_plugin.dll`) file. Move it into SGDK's `tools` folder, along 
with the `optimize_lst.py` file.

### Execution
- Open SGDK's `makefile.gen`:
  - Add next line after the inclusion of **common.mk**:  
     `PLUGIN_PARAM := -fplugin=$(GDK)/tools/optimizer_plugin.so -fplugin-arg-optimizer_plugin-disable=0 -fplugin-arg-optimizer_plugin-keep-files=0`
  - Add `$(PLUGIN_PARAM)` to the target:  
     `$(OUT_DIR)/rom.out: $(OUT_DIR)/sega.o $(OUT_DIR)/cmd_ \$(LIBMD)`  
	 Eg:
	 ```
	 $(OUT_DIR)/rom.out: $(OUT_DIR)/sega.o $(OUT_DIR)/cmd_ $(LIBMD)
	 	@$(MKDIR) -p $(dir $@)
	 	$(CC) $(PLUGIN_PARAM) -m68000 -B$(BIN) -n -T $(GDK)/md.ld -nostdlib $(OUT_DIR)/sega.o @$(OUT_DIR)/cmd_ $(LIBMD) $(LIBGCC) -o $(OUT_DIR)/rom.out -Wl,--gc-sections -flto -flto=auto -ffat-lto-objects
	 	@$(RM) $(OUT_DIR)/cmd_
	 ```
- Make sure python is in your PATH.
- Build your project:
  - `make -f $GDK/makefile.gen release -j1`

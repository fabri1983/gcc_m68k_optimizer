## GCC M68K Assembler Optimizer

Only useful for the [SGDK](https://github.com/Stephane-D/SGDK) framework, which it builds m68k elf artifacts prior 
to the final binary build.

This Python script is intended to be executed with gcc plugin feature at `PLUGIN_FINISH` phase which is 
the last opportunity we have before exiting gcc and start the linking phase.

At `PLUGIN_FINISH` phase we can access all the m68k assembly code generated from all the .c units in our project and 
the SGDK library, including the inline asm blocks.

The optimization depends heavily on the project you run it over. On some of them it saves 1% of CPU per frame 
(approximately 2 scanlines), which is a sign that the project's hot path might be better rewritten in asm (if not already).

See ![optimize_lst.py](optimize_lst.py "optimize_lst.py") at header section for a list of all peepholes and switches 
the optimizer provides.

### Build gcc and the plugin

First you need to build your gcc toolchain with plugin support enabled. This is straight forward on Linux systems, 
even on WSL (Windows Subsytem for Linux), but impossible on Windows systems (I couldn't build it yet).  
Add the toolchain into your PATH (or copy it into SGDK's `bin` folder) so SGDK can see it.

Then you need to compile the gcc plugin `optimizer_plugin.c`, responsible to execute the python script 
over the gcc m68k assembly code. See script .  
This will generate `optimizer_plugin.so` (or `optimizer_plugin.dll`) file. Move it into SGDK's `tools` folder, along 
with the `optimize_lst.py` file.

### Execution
- Open SGDK's `makefile.gen`:
  - Add next line after the inclusion of _common.mk_:  
     `PLUGIN_PARAM := -fplugin=$(GDK)/tools/optimizer_plugin.so -fplugin-arg-optimizer_plugin-disable=0 -fplugin-arg-optimizer_plugin-keep-files=0`
  - Add `$(PLUGIN_PARAM)` to the target:  
     `$(OUT_DIR)/rom.out: \$(OUT_DIR)/sega.o \$(OUT_DIR)/cmd_ \$(LIBMD)`
- Make sure python is in your PATH.
- Build your project:
  - `make -f $GDK/makefile.gen release -j1`

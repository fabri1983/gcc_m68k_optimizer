## Compile python script into C

Using python 3.10 and cython 3 let's compile our python scripts into cython c files and then link them with the plugin in a big static linked program.

`sudo apt update`

`sudo apt install -y cython3`

Build libpython3.10.a static lib from source into `/opt/python3.10-static`  
`build_python_static_lib.sh`

copy files `optimize_lst.py` and `optimize_mul_patterns.py` into this folder.

`build_plugin_full_c.sh`

It creates an static executable `optimize_lst_exe` which will be invoked by the plugin lib `optimizer_plugin.so`.

Place `optimize_lst_exe` and `optimizer_plugin.so` into SGDK's `tools` folder.

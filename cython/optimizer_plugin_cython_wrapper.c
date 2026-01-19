#include <Python.h>
#include "optimizer_plugin_cython_wrapper.h"
#include "optimize_lst_c_wrapper.h"

int optimize_file_cython_wrapper(const char *input_filename,
								const char *output_filename,
								const char *symbols_opt_filename,
								const char *symbols_canonical_filename)
{
	Py_Initialize();
	PyGILState_STATE gstate = PyGILState_Ensure();

	int ret = c_optimize_file(input_filename, output_filename, symbols_opt_filename, symbols_canonical_filename);

	PyGILState_Release(gstate);
	Py_Finalize();

	return ret;
}

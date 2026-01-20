#include <Python.h>
#include <stdio.h>
#include <stdlib.h>
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

/*
 * Executable entry point
 *
 * Supported invocations:
 *   optimize_lst_exe <input> <output>
 *   optimize_lst_exe <input> <output> <symbols_opt>
 *   optimize_lst_exe <input> <output> <symbols_opt> <symbols_canonical>
 */
int main(int argc, char **argv)
{
    const char *input = NULL;
    const char *output = NULL;
    const char *symbols_opt = NULL;
    const char *symbols_canonical = NULL;

    if (argc < 3 || argc > 5) {
        fprintf(stderr,
                "Usage:\n"
                "  %s <input> <output>\n"
                "  %s <input> <output> <symbols_opt>\n"
                "  %s <input> <output> <symbols_opt> <symbols_canonical>\n",
                argv[0], argv[0], argv[0]);
        return 1;
    }

    input  = argv[1];
    output = argv[2];

    if (argc >= 4) {
        symbols_opt = argv[3];
    }
    if (argc == 5) {
        symbols_canonical = argv[4];
    }

    return optimize_file_cython_wrapper(
        input,
        output,
        symbols_opt,
        symbols_canonical
    );
}

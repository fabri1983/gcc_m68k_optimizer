# optimize_lst_c_wrapper.pyx
# distutils: language = c
# cython: language_level=3

from libc.stdlib cimport malloc, free
from libc.string cimport strdup

import sys
import os

# Import the Python function
from optimize_lst import optimize_file

# Export the function as public - this will generate declarations in the .h file
cdef public int c_optimize_file(const char* input_filename,
                               const char* output_filename,
                               const char* symbols_opt_filename,
                               const char* symbols_canonical_filename) except -1:
    """
    C-callable wrapper around optimize_lst.optimize_file.
    Converts C strings to Python strings and calls the Python optimize_file function.
    Returns 0 on success, -1 on exception
    """
    # Convert C strings to Python strings (handle NULL as None)
    cdef str py_input = None
    cdef str py_output = None
    cdef object py_symbols_opt = None
    cdef object py_symbols_canonical = None

    if input_filename != NULL:
        py_input = input_filename.decode('utf-8')
    if output_filename != NULL:
        py_output = output_filename.decode('utf-8')
    if symbols_opt_filename != NULL:
        py_symbols_opt = symbols_opt_filename.decode('utf-8')
    if symbols_canonical_filename != NULL:
        py_symbols_canonical = symbols_canonical_filename.decode('utf-8')

    try:
        # Call the Python function
        optimize_file(py_input, py_output, py_symbols_opt, py_symbols_canonical)
        return 0  # Success
    except Exception as e:
        # Print error to stderr
        sys.stderr.write(f"[ERROR] In c_optimize_file(): {e}\n")
        sys.stderr.flush()
        return -1  # Error code

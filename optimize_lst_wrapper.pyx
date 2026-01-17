import sys
import optimize_lst

# Public C interface (acquires GIL if needed). This creates a TRUE C-callable function
cdef public int c_optimize_file(const char* input_filename,
                            const char* output_filename,
                            const char* symbols_opt_filename,
                            const char* symbols_canonical_filename) except -1:
    """
    Public C interface - can be called from other C code
    Acquires GIL automatically
    This function can use Python objects since it has GIL
    The 'except -1' tells Cython to return -1 on Python exceptions
    """
    cdef int result

    # Convert C strings to Python strings
    if input_filename != NULL:
        py_input = input_filename.decode('utf-8')
    else:
        py_input = None
    
    if output_filename != NULL:
        py_output = output_filename.decode('utf-8')
    else:
        py_output = None
    
    if symbols_opt_filename != NULL:
        py_symbols_opt = symbols_opt_filename.decode('utf-8')
    else:
        py_symbols_opt = None
    
    if symbols_canonical_filename != NULL:
        py_symbols_canonical = symbols_canonical_filename.decode('utf-8')
    else:
        py_symbols_canonical = None
    
    try:
        # Call the Python function
        optimize_lst.optimize_file(py_input, py_output, py_symbols_opt, py_symbols_canonical)
        result = 0
    except Exception as e:
        # Print error to stderr
        print(f"[ERROR] In c_optimize_file(): {e}", file=sys.stderr)
        result = -1
    
    return result

// https://gabrieleserra.ml/blog/2020-08-27-an-introduction-to-gcc-and-gccs-plugins.html

#include <gcc-plugin.h>      // Must be first GCC header
#include <plugin-version.h>  // For gcc_version
#include <options.h>         // For global_options
#include <stdio.h>
#include <string.h>
#include <ctype.h>
#include <stdbool.h>
#include <sys/stat.h>        // For file size
#include <libgen.h>          // For dirname/basename
#include <stdlib.h>          // For system()

// ANSI color codes
#define COLOR_RED     "\033[1;31m"
#define COLOR_GREEN   "\033[1;32m"
#define COLOR_YELLOW  "\033[1;33m"
#define COLOR_BLUE    "\033[1;34m"
#define COLOR_MAGENTA "\033[1;35m"
#define COLOR_CYAN    "\033[1;36m"
#define COLOR_RESET   "\033[0m"

// Colored print macros
#define PRINT_ERROR(fmt, ...) \
    fprintf(stderr, COLOR_RED "[PLUGIN] ERROR: " fmt COLOR_RESET, ##__VA_ARGS__)

#define PRINT_WARNING(fmt, ...) \
    fprintf(stderr, COLOR_YELLOW "[PLUGIN] WARNING: " fmt COLOR_RESET, ##__VA_ARGS__)

#define PRINT_INFO(fmt, ...) \
    fprintf(stderr, "[PLUGIN] " fmt, ##__VA_ARGS__)

#define PRINT_DEBUG(fmt, ...) \
    fprintf(stderr, COLOR_CYAN "[PLUGIN] DEBUG: " fmt COLOR_RESET, ##__VA_ARGS__)

// GPL compatibility declaration
int plugin_is_GPL_compatible;

typedef struct {
	bool keep_files;
} my_callback_params_t;

// Peephole function: Read file, modify, write back
static void my_optimize_func(const char *filename, my_callback_params_t *my_params) {

    // Add additional check: filename extension must be .s
    if (!filename || strcmp(filename, "/dev/null") == 0) {
        return;  // Skip if no asm file
    }

	PRINT_INFO("Invoked\n");

    // Check if filename ends with .s
    size_t len = strlen(filename);
    if (len < 2 || strcmp(filename + len - 2, ".s") != 0) {
		PRINT_INFO("Skipped. Not an .s file: %s\n", filename);
        return;  // Skip if not .s file
    }

    // Create filename_optimized string with same name that filename but adding .opt before the extension
    void *mem_filename_optimized = xmalloc(len + 5); // +5 -> ".opt" + null terminator
	char *filename_optimized = (char*) mem_filename_optimized;
    if (!filename_optimized) {
        PRINT_ERROR("Memory allocation failed for filename_optimized\n");
        return;
    }

    strncpy(filename_optimized, filename, len - 2); // Copy without .s
    strcpy(filename_optimized + len - 2, ".opt.s");

    // Create filename_copy string with same name that filename but adding .copy before the extension
    void *mem_filename_copy = xmalloc(len + 6); // +6 -> ".opt" + null terminator
	char *filename_copy = (char*) mem_filename_copy;
    if (!filename_copy) {
        PRINT_ERROR("Memory allocation failed for filename_copy\n");
        return;
    }

    strncpy(filename_copy, filename, len - 2); // Copy without .s
    strcpy(filename_copy + len - 2, ".copy.s");

	// Keep a copy of the original file
	if (my_params->keep_files) {

		FILE *fp_copy = fopen(filename_copy, "w");
		if (!fp_copy) {
			PRINT_ERROR("Failed to open %s for writing\n", filename_copy);
			free(filename_optimized);
			free(filename_copy);
			return;
		}

		// Open the original file for reading
		FILE *fp_orig = fopen(filename, "r");
		if (!fp_orig) {
			PRINT_ERROR("Failed to open %s for reading\n", filename);
			fclose(fp_copy);
			free(filename_optimized);
			free(filename_copy);
			return;
		}
		
		// Copy content of filename into filename_copy
		char buffer[4096];
		size_t bytes_read;
		while ((bytes_read = fread(buffer, 1, sizeof(buffer), fp_orig)) > 0) {
			fwrite(buffer, 1, bytes_read, fp_copy);
		}
		
		fclose(fp_orig);
		fclose(fp_copy);
	}

    // Execute python program named optimize_lst.py with its arguments
    char command[512];
    snprintf(command, sizeof(command), "python3 $GDK/tools/optimize_lst.py \"%s\" \"%s\" 1>&2", filename, filename_optimized);

    int ret = system(command);
    if (ret != 0) {
        PRINT_ERROR("Python optimizer failed with code %d\n", ret);
        free(filename_optimized);
		free(filename_copy);
        return;
    }

    FILE *fp_opt = fopen(filename_optimized, "r");
    if (!fp_opt) {
        PRINT_ERROR("Failed to open %s for reading\n", filename_optimized);
        free(filename_optimized);
		free(filename_copy);
        return;
    }

    FILE *fp = fopen(filename, "w");
    if (!fp) {
        PRINT_ERROR("Failed to open %s for writing\n", filename);
        fclose(fp_opt);
        free(filename_optimized);
		free(filename_copy);
        return;
    }

	// Replace content of filename with content of filename_optimized
    char buffer[4096];
    size_t bytes_read;
    while ((bytes_read = fread(buffer, 1, sizeof(buffer), fp_opt)) > 0) {
        fwrite(buffer, 1, bytes_read, fp);
    }

    fclose(fp);
    fclose(fp_opt);
	if (!my_params->keep_files) {
		// Clean up the temporary optimized file
		remove(filename_optimized);
	}

    free(filename_optimized);
	free(filename_copy);
	free(my_params);

    PRINT_INFO("Optimizer executed on: %s\n", filename);
}

static void callback(void *gcc_data, void *user_data) {
	my_callback_params_t *my_params = (my_callback_params_t *) user_data;
    my_optimize_func(global_options.x_asm_file_name, my_params);
}

// Plugin entry point
int plugin_init(struct plugin_name_args *plugin_info, struct plugin_gcc_version *version) {

	// Version mismatch?
    if (!plugin_default_version_check(version, &gcc_version)) {
        PRINT_ERROR("Version mismatch in plugin_init()\n");
        return 1;
    }

	// Allocate space for user params data struct
	my_callback_params_t *my_params = (my_callback_params_t *) xmalloc(sizeof(my_callback_params_t));
	my_params->keep_files = false;

	for (int i=0; i < plugin_info->argc; i++)
    {
		// -fplugin-arg-optimizer_plugin-disable=1
		// If parameter disable is 1 or true then avoid the plugin registration
		if (strcmp(plugin_info->argv[i].key, "disable") == 0 &&
				(strcasecmp(plugin_info->argv[i].value, "true") == 0 ||
				strcasecmp(plugin_info->argv[i].value, "1") == 0))
			return 0;

		// -fplugin-arg-optimizer_plugin-keep-files=1
		// If parameter keep-files is 1 or true then set user params struct accordingly
		if (strcmp(plugin_info->argv[i].key, "keep-files") == 0 &&
				(strcasecmp(plugin_info->argv[i].value, "true") == 0 ||
				strcasecmp(plugin_info->argv[i].value, "1") == 0))
			my_params->keep_files = true;
    }
	
    register_callback(plugin_info->base_name, PLUGIN_FINISH, callback, (void *)my_params);

    return 0;
}
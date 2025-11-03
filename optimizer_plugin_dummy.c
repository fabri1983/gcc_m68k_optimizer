// https://gabrieleserra.ml/blog/2020-08-27-an-introduction-to-gcc-and-gccs-plugins.html

#include <gcc-plugin.h>      // Must be first GCC header
#include <plugin-version.h>  // For gcc_version
#include <options.h>         // For global_options
#include <stdio.h>
#include <string.h>
#include <sys/stat.h>        // For file size

// GPL compatibility declaration
int plugin_is_GPL_compatible;

// Peephole function: Read file, modify, write back
static void peephole_optimize(const char *filename) {
    if (!filename || strcmp(filename, "/dev/null") == 0) {
        return;  // Skip if no asm file
    }

    FILE *fp = fopen(filename, "r");
    if (!fp) {
        fprintf(stderr, "[PLUGIN] ERROR: Failed to open %s for reading\n", filename);
        return;
    }

    // Get file size
    fseek(fp, 0, SEEK_END);
    long size = ftell(fp);
    fseek(fp, 0, SEEK_SET);

    // Read content
    void *mem = xmalloc(size + 1);
	char *content = (char*)mem;
    if (!content) {
		fprintf(stderr, "[PLUGIN] ERROR: Failed to read %s\n", filename);
        fclose(fp);
        return;
    }
    fread(content, 1, size, fp);
    content[size] = '\0';
    fclose(fp);

    // Apply peephole over content

    // Write back
    fp = fopen(filename, "w");
    if (!fp) {
        fprintf(stderr, "[PLUGIN] ERROR: Failed to open %s for writing\n", filename);
        free(content);
        return;
    }
    fwrite(content, 1, size, fp);  // Size may change; adjust if insertions/deletions
    fclose(fp);

    free(content);

    fprintf(stderr, "[PLUGIN] Optimizer executed on: %s\n", filename);
}

// PLUGIN_FINISH callback
static void finish_callback(void *gcc_data, void *user_data) {
    peephole_optimize(global_options.x_asm_file_name);
}

// Plugin entry point
int plugin_init(struct plugin_name_args *plugin_info, struct plugin_gcc_version *version) {
    if (!plugin_default_version_check(version, &gcc_version)) {
		fprintf(stderr, "[PLUGIN] ERROR: Version mismatch in plugin_init()\n");
        return 1;  // Version mismatch
    }

    register_callback(plugin_info->base_name, PLUGIN_FINISH, finish_callback, NULL);
    return 0;
}
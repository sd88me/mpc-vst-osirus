/* The mpc-vst-plugins engine interface (wrapper/engine.h) on top of virus_plugin.cpp's Schwung-style plugin API. Same
 * mapping as adapters/schwung/schwung_engine.c in mpc-vst-plugins; it lives here because this port's parameter list is
 * its own params.json (generated from virus_plugin.cpp's table), not a Schwung module.json, so build_port.sh does not
 * link that adapter. */
#include <cstdint>
extern "C" {
#include "engine.h"
}

extern "C" {
typedef struct {
    uint32_t api_version;
    void *(*create_instance)(const char *module_dir, const char *json_defaults);
    void (*destroy_instance)(void *instance);
    void (*on_midi)(void *instance, const uint8_t *msg, int len, int source);
    void (*set_param)(void *instance, const char *key, const char *val);
    int (*get_param)(void *instance, const char *key, char *buf, int buf_len);
    int (*get_error)(void *instance, char *buf, int buf_len);
    void (*render_block)(void *instance, int16_t *out_lr, int frames);
} plugin_api_v2_t;
plugin_api_v2_t *move_plugin_init_v2(const void *host);
}

static const int MIDI_SOURCE_EXTERNAL = 2;
static plugin_api_v2_t *api;

static void *eng_create(const char *dir) { return api->create_instance(dir ? dir : "", nullptr); }
static void eng_destroy(void *i) { api->destroy_instance(i); }
static void eng_midi(void *i, const uint8_t *m, int n) { api->on_midi(i, m, n, MIDI_SOURCE_EXTERNAL); }
static void eng_set(void *i, const char *k, const char *v) { api->set_param(i, k, v); }
static int eng_get(void *i, const char *k, char *b, int n) { return api->get_param(i, k, b, n); }
static void eng_render(void *i, int16_t *out, int frames) { api->render_block(i, out, frames); }

static const mpc_engine_t engine = { eng_create, eng_destroy, eng_midi, eng_set, eng_get, eng_render };

extern "C" const mpc_engine_t *mpc_engine(void) {
    if (!api) api = move_plugin_init_v2(nullptr);
    return api ? &engine : nullptr;
}

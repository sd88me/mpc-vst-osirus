// Engine-level test through the same interface the wrapper uses (mpc_engine): boots a ROM from <dir>/roms, plays
// notes, changes bank and preset, checks the state chunk fits the wrapper's 8192-byte buffer and restores.
// usage: osirus_engine_test <data dir with roms/> [seconds of audio per phase]
extern "C" {
#include "engine.h"
}
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <thread>

static int fails = 0;
#define CHECK(c, ...) do { if (c) printf("ok   " __VA_ARGS__); else { printf("FAIL " __VA_ARGS__); fails++; } printf("\n"); } while (0)

static std::string get(const mpc_engine_t *e, void *i, const char *k) {
    char b[8192] = {0};
    if (e->get_param(i, k, b, sizeof b) <= 0) return "";
    return b;
}

static double render_rms(const mpc_engine_t *e, void *i, double secs, double *peak = nullptr)
{
    int16_t buf[256];
    double sq = 0, pk = 0; long n = 0;
    const int blocks = (int)(secs * 44100 / 128);
    auto t0 = std::chrono::steady_clock::now();
    for (int b = 0; b < blocks; b++) {
        e->render(i, buf, 128);
        for (int k = 0; k < 256; k++) { double v = buf[k] / 32768.0; sq += v * v; if (fabs(v) > pk) pk = fabs(v); n++; }
        // pace like a host would, or the emulator thread never gets ahead of the ring
        std::this_thread::sleep_until(t0 + std::chrono::microseconds((long)((b + 1) * 128 * 1e6 / 44100)));
    }
    if (peak) *peak = pk;
    return sqrt(sq / n);
}

int main(int argc, char **argv)
{
    if (argc < 2) { fprintf(stderr, "usage: %s <data dir> [seconds]\n", argv[0]); return 2; }
    const double secs = argc > 2 ? atof(argv[2]) : 1.5;
    const mpc_engine_t *e = mpc_engine();
    CHECK(e != nullptr, "mpc_engine()");
    void *i = e->create(argv[1]);
    CHECK(i != nullptr, "create");

    int waited = 0;
    while (get(e, i, "is_loading") == "1" && waited < 600) { std::this_thread::sleep_for(std::chrono::milliseconds(100)); waited++; }
    printf("boot took %.1f s: %s, model %s, status \"%s\"\n", waited / 10.0, get(e, i, "rom_name").c_str(),
           get(e, i, "rom_model").c_str(), get(e, i, "loading_status").c_str());
    CHECK(get(e, i, "is_loading") == "0", "boot finished");
    CHECK(atoi(get(e, i, "bank_count").c_str()) >= 1, "bank_count %s", get(e, i, "bank_count").c_str());
    printf("preset %s \"%s\" bank \"%s\"\n", get(e, i, "preset").c_str(), get(e, i, "preset_name").c_str(), get(e, i, "bank_name").c_str());

    double pk = 0;
    render_rms(e, i, 0.5);                       // let the ring settle
    uint8_t on[3] = {0x90, 60, 100}, off[3] = {0x80, 60, 0};
    e->midi(i, on, 3);
    double rms = render_rms(e, i, secs, &pk);
    CHECK(rms > 0.001, "note 60 -> rms %.4f peak %.3f", rms, pk);
    e->midi(i, off, 3);
    render_rms(e, i, 1.0);
    printf("%s\n", get(e, i, "debug_info").c_str());
    printf("stats: %s\n", get(e, i, "engine_stats").c_str());

    // another preset sounds and changes the name
    std::string n0 = get(e, i, "preset_name");
    e->set_param(i, "preset", "17");
    std::this_thread::sleep_for(std::chrono::milliseconds(300));
    render_rms(e, i, 0.3);
    std::string n1 = get(e, i, "preset_name");
    CHECK(get(e, i, "preset") == "17" && n1 != n0, "preset 17 -> \"%s\" (was \"%s\")", n1.c_str(), n0.c_str());
    e->midi(i, on, 3);
    rms = render_rms(e, i, secs, &pk);
    e->midi(i, off, 3);
    CHECK(rms > 0.001, "preset 17 note -> rms %.4f peak %.3f", rms, pk);

    // bank change
    if (atoi(get(e, i, "bank_count").c_str()) > 1) {
        e->set_param(i, "bank_index", "1");
        std::this_thread::sleep_for(std::chrono::milliseconds(300));
        render_rms(e, i, 0.3);
        CHECK(get(e, i, "bank_index") == "1", "bank_index 1 -> \"%s\" / \"%s\"", get(e, i, "bank_name").c_str(), get(e, i, "preset_name").c_str());
    }

    // a parameter moves the engine's value
    e->set_param(i, "cutoff", "20");
    std::this_thread::sleep_for(std::chrono::milliseconds(100));
    render_rms(e, i, 0.2);
    CHECK(get(e, i, "cutoff") == "20", "cutoff -> %s", get(e, i, "cutoff").c_str());

    // BANKS page tiles
    CHECK(get(e, i, "bank_slot_1") == "BANK A" && get(e, i, "bank_slot_2_on") == "1" && get(e, i, "bank_slot_1_on") == "0", "bank tiles %s/%s",
          get(e, i, "bank_slot_1").c_str(), get(e, i, "bank_slot_2").c_str());
    e->set_param(i, "patch_slot_3", "1");
    std::this_thread::sleep_for(std::chrono::milliseconds(300));
    CHECK(get(e, i, "preset") == "2" && get(e, i, "patch_slot_3_on") == "1", "patch tile 3 -> preset %s \"%s\"", get(e, i, "preset").c_str(), get(e, i, "patch_slot_3").c_str());
    e->set_param(i, "patch_page_next", "1");
    CHECK(get(e, i, "patch_page_text") == "PAGE 2 / 5" && get(e, i, "patch_slot_1") .rfind("031", 0) == 0, "page 2: %s, first tile \"%s\"", get(e, i, "patch_page_text").c_str(), get(e, i, "patch_slot_1").c_str());
    e->set_param(i, "patch_slot_1", "1");
    std::this_thread::sleep_for(std::chrono::milliseconds(300));
    CHECK(get(e, i, "preset") == "30", "tile on page 2 -> preset %s", get(e, i, "preset").c_str());
    e->set_param(i, "bank_slot_1", "1");
    std::this_thread::sleep_for(std::chrono::milliseconds(300));
    CHECK(get(e, i, "bank_index") == "0", "bank tile 1 -> bank %s", get(e, i, "bank_index").c_str());
    e->set_param(i, "patch_page_prev", "1"); e->set_param(i, "patch_page_prev", "1");
    CHECK(get(e, i, "patch_page_text") == "PAGE 1 / 5", "page clamps at 1: %s", get(e, i, "patch_page_text").c_str());

    // INIT button: the ROM's own init single
    e->set_param(i, "init_patch", "1");
    std::this_thread::sleep_for(std::chrono::milliseconds(400));
    CHECK(get(e, i, "bank_index") == "0" && get(e, i, "preset") == "126" && get(e, i, "preset_name").find("Init") != std::string::npos, "INIT -> bank %s preset %s \"%s\"",
          get(e, i, "bank_index").c_str(), get(e, i, "preset").c_str(), get(e, i, "preset_name").c_str());

    // state
    const std::string cut0 = get(e, i, "cutoff"), bank0 = get(e, i, "bank_index"), pre0 = get(e, i, "preset");
    std::string st = get(e, i, "state");
    CHECK(!st.empty() && st.size() < 8000, "state %zu bytes (wrapper buffer 8192)", st.size());
    e->destroy(i);
    i = e->create(argv[1]);
    e->set_param(i, "state", st.c_str());      // while booting: replayed once the emulator is up
    waited = 0;
    while (get(e, i, "is_loading") == "1" && waited < 600) { std::this_thread::sleep_for(std::chrono::milliseconds(100)); waited++; }
    std::this_thread::sleep_for(std::chrono::milliseconds(800));
    render_rms(e, i, 0.5);
    CHECK(get(e, i, "cutoff") == cut0 && get(e, i, "bank_index") == bank0 && get(e, i, "preset") == pre0, "state restored cutoff %s bank %s preset %s",
          get(e, i, "cutoff").c_str(), get(e, i, "bank_index").c_str(), get(e, i, "preset").c_str());
    e->destroy(i);
    printf(fails ? "FAILED\n" : "PASSED\n");
    return fails ? 1 : 0;
}

// Soak test: changes patches the way a player browsing sounds does, with a chord held, in real time, and prints the engine's own counters
// every few seconds so a slow growth (CPU, memory, threads, dropouts) shows.
// usage: osirus_soak <data dir with roms/> [minutes] [seconds per patch]
extern "C" {
#include "engine.h"
}
#include <chrono>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <dirent.h>
#include <string>
#include <thread>
#include <unistd.h>

static std::string get(const mpc_engine_t *e, void *i, const char *k) {
    char b[8192] = {0};
    if (e->get_param(i, k, b, sizeof b) <= 0) return "";
    return b;
}
static long rss_kb() { long a = 0, r = 0; FILE *f = fopen("/proc/self/statm", "r"); if (f) { if (fscanf(f, "%ld %ld", &a, &r) != 2) r = 0; fclose(f); } return r * (sysconf(_SC_PAGESIZE) / 1024); }
static int nthreads() { int n = 0; if (DIR *d = opendir("/proc/self/task")) { while (dirent *x = readdir(d)) if (x->d_name[0] != '.') n++; closedir(d); } return n; }

int main(int argc, char **argv) {
    if (argc < 2) { fprintf(stderr, "usage: %s <data dir> [minutes] [seconds per patch]\n", argv[0]); return 2; }
    const double minutes = argc > 2 ? atof(argv[2]) : 5, per_patch = argc > 3 ? atof(argv[3]) : 1.0;
    const mpc_engine_t *e = mpc_engine();
    void *i = e->create(argv[1]);
    for (int w = 0; get(e, i, "is_loading") == "1" && w < 600; w++) std::this_thread::sleep_for(std::chrono::milliseconds(100));
    printf("%s, status \"%s\"\n", get(e, i, "rom_name").c_str(), get(e, i, "loading_status").c_str());
    const int presets = atoi(get(e, i, "preset_count").c_str());
    int16_t buf[256];
    const int chord[6] = {48, 55, 60, 64, 67, 72};
    auto t0 = std::chrono::steady_clock::now();
    long blocks = 0, next_report = 0, patch = 0, nextpatch = 0;
    const long total = (long)(minutes * 60 * 44100 / 128), per = (long)(per_patch * 44100 / 128);
    printf("%d presets, %.1f min, patch every %.1f s\n", presets, minutes, per_patch);
    printf("  min   rss_kb thr patch  %s\n", "stats / debug");
    for (; blocks < total; blocks++) {
        if (blocks >= nextpatch) {
            for (int n : chord) { uint8_t m[3] = {0x80, (uint8_t)n, 0}; e->midi(i, m, 3); }
            patch++;
            e->set_param(i, "preset", std::to_string((patch * 7) % (presets > 0 ? presets : 128)).c_str());
            for (int n : chord) { uint8_t m[3] = {0x90, (uint8_t)n, 120}; e->midi(i, m, 3); }
            nextpatch = blocks + per;
        }
        e->render(i, buf, 128);
        std::this_thread::sleep_until(t0 + std::chrono::microseconds((long)((blocks + 1) * 128 * 1e6 / 44100)));
        if (blocks >= next_report) {
            printf("%5.1f %8ld %3d %5ld  %s | %s\n", blocks * 128 / 44100.0 / 60, rss_kb(), nthreads(), patch, get(e, i, "engine_stats").c_str(), get(e, i, "debug_info").c_str());
            fflush(stdout);
            next_report = blocks + (long)(15 * 44100 / 128);
        }
    }
    e->destroy(i);
    return 0;
}

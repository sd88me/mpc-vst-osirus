// tests/make_legacy_chunk.sh: drive the released 0.2.11 build (1.x wrapper + engine, x86) like a host and save its effGetChunk.
// Bank B, preset 18, CUTOFF 40, OCTAVE +1, OUTPUT LEVEL 55.
#include <dlfcn.h>
#include <chrono>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <thread>

struct AEffect;
typedef intptr_t (*cb)(AEffect*, int32_t, int32_t, intptr_t, void*, float);
struct AEffect {
    int32_t magic;
    intptr_t (*d)(AEffect*, int32_t, int32_t, intptr_t, void*, float);
    void* proc;
    void (*setP)(AEffect*, int32_t, float);
    float (*getP)(AEffect*, int32_t);
    int32_t np, npar, ni, no, flags;
    intptr_t r1, r2;
    int32_t a, b, c;
    float io;
    void *obj, *user;
    int32_t uid, ver;
    void (*pr)(AEffect*, float**, float**, int32_t);
};
static intptr_t host(AEffect*, int32_t op, int32_t, intptr_t, void*, float) { return op == 1 ? 2400 : 0; }

static void run(AEffect* e, int blocks)
{
    float L[128], R[128], *out[2] = {L, R};
    for (int i = 0; i < blocks; i++) { e->pr(e, nullptr, out, 128); std::this_thread::sleep_for(std::chrono::microseconds(2900)); }
}

int main(int argc, char** argv)
{
    if (argc < 3) return 2;
    void* h = dlopen(argv[1], RTLD_NOW);
    if (!h) { std::fprintf(stderr, "%s\n", dlerror()); return 1; }
    auto main_ = (AEffect* (*)(cb))dlsym(h, "VSTPluginMain");
    AEffect* e = main_(host);
    std::printf("0.2.11: uid=%x params=%d\n", e->uid, e->npar);
    e->d(e, 10, 0, 0, nullptr, 44100.f);
    e->d(e, 11, 0, 128, nullptr, 0);
    e->d(e, 12, 0, 1, nullptr, 0);
    char disp[128] = {0};
    for (int t = 0; t < 300; t++)   // up to ~30 s for the boot
    {
        run(e, 34);
        e->d(e, 7, 12, 0, disp, 0);  // loading_status
        if (!std::strncmp(disp, "Ready", 5)) break;
    }
    std::printf("status: %s\n", disp);
    e->setP(e, 0, 1.0f / 31.0f);      // BANK B (0.2.11: bank_index 0..31)
    run(e, 200);
    e->setP(e, 1, 17.0f / 127.0f);    // PRESET 18
    run(e, 400);
    e->setP(e, 38, 40.0f / 127.0f);   // CUTOFF 40 (an edit of the sound)
    e->setP(e, 8, 5.0f / 8.0f);       // OCTAVE +1
    e->setP(e, 15, 54.0f / 99.0f);    // OUTPUT LEVEL 55
    run(e, 300);
    e->d(e, 7, 3, 0, disp, 0);       // preset_name
    std::printf("preset: %s\n", disp);
    void* chunk = nullptr;
    const intptr_t n = e->d(e, 23, 0, 0, &chunk, 0);
    if (n <= 0 || !chunk) { std::fprintf(stderr, "no chunk\n"); return 1; }
    FILE* f = std::fopen(argv[2], "wb");
    std::fwrite(chunk, 1, (size_t)n, f);
    std::fclose(f);
    std::printf("wrote %s (%ld bytes): %.120s...\n", argv[2], (long)n, (const char*)chunk);
    e->d(e, 12, 0, 0, nullptr, 0);
    e->d(e, 1, 0, 0, nullptr, 0);
    return 0;
}

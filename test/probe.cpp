// Headless proof of life: load a Virus ROM from <dir>, boot the emulated DSP, play a note, render audio.
// usage: osirus_probe <rom dir> [seconds]
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <string>
#include <vector>

#include "virusLib/device.h"
#include "virusLib/dspSingle.h"
#include "virusLib/microcontroller.h"
#include "virusLib/romfile.h"
#include "virusLib/romloader.h"
#include "synthLib/audioTypes.h"
#include "synthLib/midiTypes.h"
#include "dsp56kEmu/audio.h"

static const int CHUNK = 64;

int main(int argc, char **argv)
{
    if (argc < 2) { fprintf(stderr, "usage: %s <rom dir> [seconds]\n", argv[0]); return 2; }
    const double secs = argc > 2 ? atof(argv[2]) : 3.0;
    auto roms = virusLib::ROMLoader::findROMs(std::string(argv[1]));
    printf("roms found: %zu\n", roms.size());
    if (roms.empty()) return 1;
    auto *rom = new virusLib::ROMFile(std::move(roms[0]));
    printf("rom: %s model %s\n", rom->getFilename().c_str(), rom->getModelName().c_str());

    virusLib::DspSingle *d1 = nullptr, *d2 = nullptr;
    virusLib::Device::createDspInstances(d1, d2, *rom, 46875.0f);
    auto *mc = new virusLib::Microcontroller(*d1, *rom, false);
    d1->getAudio().setCallback([&](dsp56k::Audio*) { mc->getMidiQueue(0).onAudioWritten(); }, 0);
    virusLib::Device::bootDSPs(d1, d2, *rom, false);

    float l[CHUNK], r[CHUNK];
    synthLib::TAudioInputs in = {};
    synthLib::TAudioOutputs out = {};
    out[0] = l; out[1] = r;
    for (int i = 0; i < 32; i++) d1->processAudio(in, out, 8, 0);
    if (rom->getModel() == virusLib::DeviceModel::A) d1->disableESSI1();
    mc->sendInitControlCommands(127);
    for (int i = 0; i < 8; i++) d1->processAudio(in, out, 8, 0);
    mc->createDefaultState();
    for (int i = 0; i < 8; i++) d1->processAudio(in, out, 8, 0);
    printf("booted\n");

    synthLib::SMidiEvent on(synthLib::MidiEventSource::Host, 0x90, 60, 100);
    mc->sendMIDI(on);
    const int total = (int)(secs * 46875.0 / CHUNK);
    double peak = 0; double sq = 0; long n = 0;
    auto t0 = std::chrono::steady_clock::now();
    for (int b = 0; b < total; b++) {
        d1->processAudio(in, out, CHUNK, CHUNK);
        for (int i = 0; i < CHUNK; i++) {
            double a = fabs(l[i]); if (a > peak) peak = a;
            sq += (double)l[i] * l[i]; n++;
        }
    }
    double dt = std::chrono::duration<double>(std::chrono::steady_clock::now() - t0).count();
    printf("rendered %.2fs audio in %.2fs wall (%.2fx realtime) peak %.4f rms %.4f\n", secs, dt, secs / dt, peak, sqrt(sq / n));
    return peak > 0.001 ? 0 : 3;
}

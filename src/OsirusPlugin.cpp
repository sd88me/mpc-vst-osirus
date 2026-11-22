// Osirus for MPC: the native front end (framework/mpc_plugin.h) around the Osirus engine (src/dsp/virus_plugin.cpp + mpc_engine.cpp:
// gearmulator's Access Virus A/B/C emulation on its own emulator thread, pinned to the fast cores, rendering 44.1 kHz int16 stereo into a
// ring that runs ahead of the host).
//
// Signal flow: host MIDI (sample accurate) -> engine midi -> engine render (drains the ring) -> float outputs, through a linear
// resampler when the host does not run at 44.1 kHz.
//
// Parameters: the released 0.2.11 wrapper build's 300 in the same order, then appended keys (params.lock -> tools/gen_sdk_params.py -> params_gen.h).
//   * value params (kPolled): a host change goes to the engine as its own key, options as their index. Whole numbers and options
//     settle toward the direction of a move, so a small Q-Link turn moves one step (the 1.x rule). A sound / bank load or a state load
//     bumps the engine's "display_rev": the worker then reads every value back and tells the host.
//   * momentary verbs (kMomentary): 0 -> 1 fires once, then the param drops back to 0. BANK / PRESET < > (kStep) are the engine's own
//     verbs; list tiles (kTile, BANKS page) fire on a tap and are lit from the engine's "<key>_on".
//   * text readouts (kText): the value text is the engine's text; the value is a counter bumped when the text changes, because the
//     host only re-reads a param's text when its value moves.
//   * favourites: the engine keeps them (<data dir>/favourites.dat, whole singles), as in 0.2.11. They are the MPC's PRESET
//     menu (VST programs 0..63 = the engine's "favourite" slots, named by "fav_name:<n>"); +FAV / -FAV are the engine's verbs.
//   * ui_open (kUi): which drawn pick-list the skin shows; the reserved slots (kReserved) hold the 1.x popup flags' indices.
// Parameter 0 is BANK. The host nudges parameter 0 on every prepare: a change applies only after it has held for ~40 ms.
// State: the engine's own "state" JSON is the truth; it travels as the MPC chunk's extra state, and nothing is written to the engine
// while the MPC chunk restores parameter values. A project saved by the 1.x wrapper build stored only that JSON as its chunk: it is
// still read (effSetChunk is wrapped below). The MPC hands the chunk over before the emulator has booted: the last state given is
// kept and returned from a save until the engine is ready.

#include "mpc_plugin.h"

extern "C" {
#include "engine.h"
}
#include "params_gen.h"

#include <sys/stat.h>
#include <dirent.h>

#include <algorithm>
#include <atomic>
#include <chrono>
#include <cmath>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <fstream>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#ifndef OSIRUS_NAME
#define OSIRUS_NAME "Osirus"
#endif
#ifndef OSIRUS_UID
#define OSIRUS_UID 'O', 's', 'r', 'S'
#endif
#define OSIRUS_FOURCC(...) MPC_FOURCC(__VA_ARGS__)   // expands OSIRUS_UID before MPC_FOURCC counts its arguments
#ifndef OSIRUS_VERSION
#define OSIRUS_VERSION 1000
#endif

namespace {

const int kEngineRate = 44100;
const int kChunk = 128;
const int kStateMax = 8192;   // the engine's state is ~4.8 kB (header, the 512-byte single as hex, every parameter); the 1.x wrapper's buffer

mpc::PluginInfo makeInfo()
{
    mpc::PluginInfo i;
    i.name = OSIRUS_NAME;
    i.vendor = "sd88me";
    i.uniqueId = OSIRUS_FOURCC(OSIRUS_UID);
    i.version = OSIRUS_VERSION;
    i.isInstrument = true;
    i.numInputs = 0;
    i.numOutputs = 2;
    return i;
}

long long nowMs()
{
    return std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now().time_since_epoch()).count();
}

uint32_t fnv(const char* s)
{
    uint32_t h = 2166136261u;
    for (; *s; ++s) h = (h ^ (unsigned char)*s) * 16777619u;
    return h;
}

// a ROM in a roms/ folder: any file but the PUT_..._HERE.txt placeholder and readme
bool hasRom(const std::string& dir)
{
    DIR* d = opendir(dir.c_str());
    if (!d) return false;
    bool any = false;
    while (dirent* e = readdir(d))
    {
        const std::string n = e->d_name;
        if (n == "." || n == ".." || n.rfind("PUT_", 0) == 0 || n == "readme.txt") continue;
        any = true;
        break;
    }
    closedir(d);
    return any;
}

bool isState(const std::string& s) { return s.size() > 2 && s[0] == '{' && s.find("\"state_version\"") != std::string::npos; }

thread_local int t_pushing = -1;   // the parameter the worker is telling the host about right now (its echo is ignored)

} // namespace

class OsirusPlugin : public mpc::Plugin
{
public:
    OsirusPlugin() : mpc::Plugin(makeInfo())
    {
        for (int i = 0; i < kNumParams; ++i)
        {
            const PSpec& s = g_pspecs[i];
            mpc::Param p = (s.flags & kChoice)
                ? mpc::choiceParam(s.key, s.name, std::vector<std::string>(s.choices, s.choices + s.nchoices), (int)s.def)
                : mpc::intParam(s.key, s.name, (int)s.min, (int)s.max, (int)s.def);
            p.automatable = !(s.flags & kNoAuto);
            addParam(p);
        }
        const size_t n = (size_t)kNumParams;
        held_ = new std::atomic<bool>[n];
        release_ = new std::atomic<bool>[n];
        hostMoved_ = new std::atomic<bool>[n];
        hostAt_ = new std::atomic<long long>[n];
        told_ = new std::atomic<float>[n];
        for (size_t i = 0; i < n; ++i)
        {
            held_[i].store(false); release_[i].store(false); hostMoved_[i].store(false);
            hostAt_[i].store(0); told_[i].store(-1.0e9f);
        }
        lastPos_.assign(n, -1.0f);
        textHash_.assign(n, 0u);

        // The engine reads <data dir>/roms/ and keeps banks/ and favourites.dat there. As in 0.2.11 (MODULE_SUBDIR), the data dir is
        // osirus/ next to the .so: <folder>/osirus for the catalog install (osirus.so at the folder root), <folder>/VST/osirus for the
        // SDK folder (VST/osirus-arm64.so). MPC_PLUGIN_FOLDER (tests) is the folder.
        const char* env = std::getenv("MPC_PLUGIN_FOLDER");
        const std::string lib = mpc::detail::libraryPath();
        const std::string soDir = lib.empty() ? mpc::detail::computePluginFolder() : mpc::detail::parentOf(mpc::detail::normaliseSlashes(lib));
        dataDir_ = (env && env[0] ? std::string(env) + "/VST" : soDir) + "/osirus";
        // a folder whose ROM sits in the other layout's place (an SDK folder copied over a catalog install, or the reverse): use that
        if (!(env && env[0]) && !hasRom(dataDir_ + "/roms"))
        {
            const std::string folder = mpc::detail::computePluginFolder();
            for (const std::string& old : {folder + "/osirus", folder + "/VST/osirus"})
                if (old != dataDir_ && hasRom(old + "/roms")) { dataDir_ = old; break; }
        }
        eng_ = mpc_engine();
        inst_ = eng_->create(dataDir_.c_str());
        for (int i = 0; i < kFavSlots; ++i) addProgram((std::to_string(i + 1) + " --").c_str(), {});
        worker_ = std::thread(&OsirusPlugin::workerMain, this);
    }

    ~OsirusPlugin() override
    {
        quit_.store(true);
        if (worker_.joinable()) worker_.join();
        if (inst_) eng_->destroy(inst_);
        delete[] held_;
        delete[] release_;
        delete[] hostMoved_;
        delete[] hostAt_;
        delete[] told_;
    }

    void prepare(double sampleRate, int) override
    {
        step_ = sampleRate > 1000 ? (double)kEngineRate / sampleRate : 1.0;
        frac_ = 0;
        have_ = 0;
    }

    void reset() override
    {
        store(kUiParam, 0.0f);
        notifyUi_.store(true);
    }

    // ---- audio ----------------------------------------------------------------------------------------------------------------
    void process(mpc::ProcessContext& ctx) override
    {
        if (!inst_) return;
        float* L = ctx.outputs[0];
        float* R = ctx.numOutputs > 1 ? ctx.outputs[1] : nullptr;
        int frame = 0, mi = 0;
        if (eng_->song_pos)   // MPC's tempo and position every block (Vavra's): the arpeggiator and synced effects follow it
        {
            const mpc::Transport& t = ctx.transport;
            const bool ok = t.ppqValid && t.tempoValid && t.bpm > 0;
            eng_->song_pos(inst_, ok ? t.ppqPos : -1.0, ok ? t.bpm : 0.0, t.playing ? 1 : 0, ctx.numFrames);
        }
        while (frame < ctx.numFrames)
        {
            while (mi < ctx.numMidiEvents && ctx.midi[mi].sampleOffset <= frame)
            {
                const mpc::MidiEvent& e = ctx.midi[mi++];
                eng_->midi(inst_, e.data, e.size);
            }
            int end = ctx.numFrames;
            if (mi < ctx.numMidiEvents) end = std::min(std::max(ctx.midi[mi].sampleOffset, frame + 1), ctx.numFrames);
            while (frame < end)
            {
                const int n = std::min(end - frame, kChunk);
                renderOut(L + frame, R ? R + frame : nullptr, n);
                frame += n;
            }
        }
    }

    // ---- parameters -----------------------------------------------------------------------------------------------------------
    void parameterChanged(int index, float plain) override
    {
        if (index < 0 || index >= kNumParams || !inst_) return;
        if (t_pushing == index) return;          // the host echoing what the worker just told it
        const PSpec& s = g_pspecs[index];
        if (s.flags & (kUi | kReserved)) return;
        if (index == kFavSave || (s.flags & kLocal)) { if (!loading_.load()) localChanged(index, plain); return; }   // +FAV opens the naming keyboard
        if (index == kRomBc)                     // B/C ROM: what the loaded ROM is (the skin hides B/C-only panels on a Virus A); the
        {                                        // engine owns it, so a host write is undone on the next worker pass (no 300 ms hold)
            hostAt_[index].store(0);
            romBcUndo_.store(true);
            hostMoved_[index].store(true);
            return;
        }
        const long long prevAt = hostAt_[index].exchange(nowMs());   // the host's previous move of it (for "a turn": see PRESET below)
        if (loading_.load()) return;             // an MPC chunk is restoring values: the engine state follows as extra state
        if ((s.flags & kChoice) && get(kUiParam) > 0.5f)   // a pick from the open drawn list closes it
        {
            store(kUiParam, 0.0f);
            notifyUi_.store(true);
        }
        if ((s.flags & kText) && !(s.flags & kTile)) return;   // a readout's counter: nothing to send
        if (s.flags & kMomentary)
        {
            if (plain < 0.5f) { held_[index].store(false); if (s.flags & kTile) hostMoved_[index].store(true); return; }
            if (held_[index].exchange(true)) return;
            if (s.flags & kStep)                 // BANK / PRESET < >: as the 1.x wrapper did, the target's current engine value + delta, clamped
            {                                    // (the engine has no verbs for them; this key itself never reaches the engine)
                const PSpec& t = g_pspecs[s.stepTarget];
                char b[32];
                if (engineGet(t.key, b, sizeof b))
                {
                    const float v = std::min(std::max((float)std::atof(b) + s.stepDelta, t.min), t.max);
                    std::snprintf(b, sizeof b, "%d", (int)std::lround(v));
                    engineSet(t.key, b);
                }
                hostMoved_[s.stepTarget].store(true);
                release_[index].store(true);
                return;
            }
            engineSet(s.key, "1");               // the engine's own verbs (tiles pick, PANIC, INIT PATCH, +FAV ...)
            if (s.flags & kTile) hostMoved_[index].store(true);   // the tile shows "<key>_on", read back by the worker
            else release_[index].store(true);
            return;
        }
        // whole numbers and options: settle toward the move, then send
        const float span = s.max - s.min;
        float v = plain;
        if (span > 0)
        {
            const float pos = getNormalised(index) * span;
            const float cur = told_[index] > -1.0e8f ? told_[index] - s.min : pos;
            float steps = settle(pos, cur, lastPos_[(size_t)index]);
            // A Q-Link or data-wheel tick on PRESET (0..255) or BANK (0..63) moves the host's value about two (half a) steps, off a step:
            // one sound / bank a tick. Originally: a tick on PRESET (0..255) moves the host's value about two steps, off a step: one sound a tick, in
            // the way the host's value moved. While the control turns the read-back waits 300 ms, so the host's value runs ahead of the
            // sound: the direction is then judged from the host's previous position, not from the sound (JV-880 2.0.1's lesson).
            const float last = lastPos_[(size_t)index];
            // At an end of the range (the host's value gets there long before the sound does) a tick is clamped onto a step: during a
            // turn (moves under 300 ms apart; a set to 0 or the top on its own is that value) it is still one sound that way, and the worker sends the sound back at once (no hold) so the control has room again.
            const bool atEnd = pos <= 0.001f || pos >= span - 0.001f;
            const bool stepped = !std::strcmp(s.key, "preset") || !std::strcmp(s.key, "bank_index");   // BANK: a tick is about half a step
            if (stepped && atEnd && nowMs() - prevAt < 300 && last >= 0 && std::fabs(pos - last) < 3.0f && pos != last)
            {
                steps = std::round(cur) + (pos > last ? 1.0f : -1.0f);
                hostAt_[index].store(0);
            }
            else if (stepped && std::fabs(pos - std::round(pos)) > 0.001f)
            {
                if (last >= 0 && std::fabs(pos - last) < 3.0f && pos != last)
                    steps = std::round(cur) + (pos > last ? 1.0f : -1.0f);
                else if (std::fabs(pos - cur) < 3.0f && pos != cur)
                    steps = std::round(cur) + (pos > cur ? 1.0f : -1.0f);
            }
            lastPos_[(size_t)index] = pos;
            steps = std::min(std::max(steps, 0.0f), span);
            v = s.min + steps;
            // Where it landed reaches the host from the worker ~10 ms later: the host's own value is left as it set it until then,
            // so a set reads back unchanged (host_sim's sweep checks that).
            if (std::fabs(getNormalised(index) * span - steps) > 0.001f) hostMoved_[index].store(true);
        }
        if (index == 0)   // debounced (see the header comment)
        {
            pend0Value_.store(v);
            pend0At_.store(nowMs());
            return;
        }
        told_[index] = v;
        sendValue(index, v);
    }

    bool formatValue(int index, float plain, std::string& out) override
    {
        (void)plain;
        if (index < 0 || index >= kNumParams) return false;
        const PSpec& s = g_pspecs[index];
        char buf[128];
        if (index == kFavName) { std::lock_guard<std::mutex> g(kbMu_); out = kbName_ + "_"; return true; }
        if (s.flags & kText) { out = engineGet(s.key, buf, sizeof buf) ? buf : ""; return true; }   // readouts and tile names
        if (s.flags & (kMomentary | kUi | kReserved)) { out = ""; return true; }
        return false;
    }

    // ---- state ----------------------------------------------------------------------------------------------------------------
    void saveExtraState(std::vector<uint8_t>& out) override
    {
        const std::string s = currentState();
        out.assign(s.begin(), s.end());
    }

    void loadExtraState(const uint8_t* data, size_t size) override
    {
        if (!data || !size) return;
        ignoreProgUntil_.store(nowMs() + 2000);   // the host re-picks the saved program after a project load: the project's sound wins
        closeKeyboard(true);                      // a project saved with the keyboard open restored kb_open = 1: push it closed
        applyState(std::string(reinterpret_cast<const char*>(data), strnlen(reinterpret_cast<const char*>(data), size)));
    }

    // A project saved by the 1.x wrapper build: its chunk is the engine's state JSON, NUL-terminated. Called from the wrapped effSetChunk.
    bool loadLegacy(const char* data, size_t size)
    {
        if (!data || !size) return false;
        const std::string s(data, strnlen(data, size));
        if (!isState(s)) return false;
        ignoreProgUntil_.store(nowMs() + 2000);
        closeKeyboard(true);
        applyState(s);
        return true;
    }

    std::atomic<bool> loading_{false};   // set around an MPC chunk load (wrapped effSetChunk)

    // ---- the naming keyboard (+FAV, as Vavra / Profit-5) ------------------------------------------------------------------------
    // +FAV: the engine takes the sound as it is now ("fav_begin"), the keyboard opens on its name (kb_open = 1, the skin shows it;
    // fav_name is the typed text); SAVE stores it under that name ("fav_save_as"), CANCEL closes.
    void localChanged(int index, float plain)
    {
        if (!(g_pspecs[index].flags & kMomentary) && index != kFavSave) return;   // kb_open / fav_name: set by the plugin only
        if (plain < 0.5f) { held_[index].store(false); return; }
        if (held_[index].exchange(true)) return;
        release_[index].store(true);   // a momentary: back to 0 on the next worker pass
        const long long now = nowMs();
        if (now - lastFire_[(size_t)index] < 250) return;   // the second report of one tap
        lastFire_[(size_t)index] = now;
        if (index == kFavSave)
        {
            if (!engineReady()) return;
            engineSet("fav_begin", "1");
            char b[64];
            std::string name = engineGet("fav_pending_name", b, sizeof b) ? b : "";
            while (!name.empty() && name.back() == ' ') name.pop_back();
            if (name.size() > (size_t)kFavNameMax) name.resize((size_t)kFavNameMax);
            { std::lock_guard<std::mutex> g(kbMu_); kbName_ = name; kbShift_ = false; }
            kbOpen_.store(true);
            kbDirty_.store(true);
            return;
        }
        if (index >= kKbFirst && index < kKbFirst + kKbCount)
        {
            if (!kbOpen_.load()) return;
            const int k = index - kKbFirst, nchars = (int)sizeof kKbChars - 1;
            if (k == nchars + 3) { closeKeyboard(); return; }   // CANCEL
            if (k == nchars + 4) { saveTyped(); return; }       // SAVE
            { std::lock_guard<std::mutex> g(kbMu_); typeKey(k); }
            kbDirty_.store(true);
        }
    }

    void typeKey(int k)   // kbMu_ held; k = 0 .. kKbCount - 1
    {
        const int nchars = (int)sizeof kKbChars - 1;
        if (k <= nchars)   // a character or space
        {
            if ((int)kbName_.size() >= kFavNameMax) return;
            char c = k < nchars ? kKbChars[k] : ' ';
            const bool cap = kbName_.empty() || kbName_.back() == ' ';
            if (c >= 'A' && c <= 'Z')
            {
                if (cap == kbShift_) c = (char)(c - 'A' + 'a');   // capital at the start and after a space; SHIFT flips the next letter
                kbShift_ = false;
            }
            kbName_ += c;
        }
        else if (k == nchars + 1) { if (!kbName_.empty()) kbName_.pop_back(); }
        else if (k == nchars + 2) kbShift_ = !kbShift_;
    }

    void closeKeyboard(bool always = false)
    {
        if (kbOpen_.exchange(false) || always) kbDirty_.store(true);
    }

    void saveTyped()
    {
        std::string name;
        { std::lock_guard<std::mutex> g(kbMu_); name = kbName_; }
        while (!name.empty() && name.back() == ' ') name.pop_back();
        if (name.empty()) name = "Favourite";
        closeKeyboard();
        engineSet("fav_save_as", name.c_str());   // the favourite count changes: refreshFavNames renames the PRESET menu's entries
    }

    // test hooks
    bool dbgKbOpen() const { return kbOpen_.load(); }
    std::string dbgKbName() { std::lock_guard<std::mutex> g(kbMu_); return kbName_; }
    void requestResync() { resync_.store(true); }

private:
    // 44.1 kHz engine -> host rate. At 44.1 kHz the engine renders straight into the output.
    void renderOut(float* L, float* R, int n)
    {
        if (std::fabs(step_ - 1.0) < 1e-9)
        {
            eng_->render(inst_, pcm_, n);
            for (int i = 0; i < n; ++i)
            {
                L[i] = pcm_[2 * i] * (1.0f / 32768.0f);
                if (R) R[i] = pcm_[2 * i + 1] * (1.0f / 32768.0f);
            }
            return;
        }
        for (int i = 0; i < n; ++i)
        {
            while (have_ < 2 || frac_ >= 1.0)   // keep two source frames: [0] at frac_ = 0, [1] at 1
            {
                if (have_ >= 2) { src_[0] = src_[2]; src_[1] = src_[3]; --have_; frac_ -= 1.0; }
                if (srcPos_ >= srcLen_) { eng_->render(inst_, pcm_, kChunk); srcPos_ = 0; srcLen_ = kChunk; }
                src_[have_ * 2] = pcm_[srcPos_ * 2] * (1.0f / 32768.0f);
                src_[have_ * 2 + 1] = pcm_[srcPos_ * 2 + 1] * (1.0f / 32768.0f);
                ++srcPos_;
                ++have_;
            }
            const float f = (float)frac_;
            L[i] = src_[0] + (src_[2] - src_[0]) * f;
            if (R) R[i] = src_[1] + (src_[3] - src_[1]) * f;
            frac_ += step_;
        }
    }

    void engineSet(const char* key, const char* val) { eng_->set_param(inst_, key, val); }

    bool engineGet(const char* key, char* buf, int n)
    {
        const int r = eng_->get_param(inst_, key, buf, n);
        if (r <= 0) { buf[0] = 0; return false; }
        buf[r < n ? r : n - 1] = 0;
        return true;
    }

    bool engineReady()
    {
        char b[8];
        return engineGet("ready", b, sizeof b) && std::atoi(b) != 0;
    }

    std::string engineState()
    {
        std::vector<char> buf((size_t)kStateMax);
        return inst_ && engineGet("state", buf.data(), kStateMax) ? std::string(buf.data()) : std::string();
    }

    // What a save stores: the engine's state once it has booted; before that the state the project gave us (it would otherwise lose
    // the edited sound, which the engine only reports once it is running).
    std::string currentState()
    {
        {
            std::lock_guard<std::mutex> g(stateMu_);
            if (!pendingState_.empty())
            {
                if (!engineReady()) return pendingState_;
                pendingState_.clear();
            }
        }
        return engineState();
    }

    void applyState(const std::string& s)
    {
        if (!inst_ || !isState(s)) return;
        engineSet("state", s.c_str());
        if (!engineReady()) { std::lock_guard<std::mutex> g(stateMu_); pendingState_ = s; }
        resync_.store(true);
    }

    void sendValue(int index, float v)
    {
        const PSpec& s = g_pspecs[index];
        const int iv = (int)std::lround(v);
        char buf[24];
        std::snprintf(buf, sizeof buf, "%d", iv);
        engineSet(s.key, buf);
    }

    // Set a parameter's value without calling parameterChanged (so it is not written back to the engine).
    void store(int i, float plain) { values_[(size_t)i]->store(param(i).toNormalised(plain), std::memory_order_relaxed); }

    // Where a whole-number / option param lands, in steps from its minimum (the 1.x wrapper's rule): a value on a step is a click,
    // a preset or automation; between steps it is a Q-Link / wheel / drag move, rounded toward the way it moves.
    static float settle(float pos, float cur, float last)
    {
        if (std::fabs(pos - std::round(pos)) <= 0.001f) return std::round(pos);
        const float dir = (last >= 0 && std::fabs(pos - last) < 0.5f) ? pos - last : pos - cur;
        if (dir == 0) return std::round(cur);
        return dir > 0 ? std::ceil(pos - 0.001f) : std::floor(pos + 0.001f);
    }

    // ---- worker: debounced parameter 0, momentary releases, everything the engine changes by itself -----------------------------
    void pushValue(int i, float plain)
    {
        told_[i] = plain;
        store(i, plain);
        t_pushing = i;
        notifyHostParameterChanged(i);
        t_pushing = -1;
    }

    void workerMain()
    {
        while (!quit_.load())
        {
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
            tickOnce(false);
        }
    }

    // One worker pass. force = the offline test: apply a pending parameter 0 now and read back everything.
    void tickOnce(bool force)
    {
        if (!inst_) return;
        const long long now = nowMs();
        ++tick_;
        const long long p0 = pend0At_.load();
        if (p0 && (force || now - p0 >= 40))
        {
            pend0At_.store(0);
            const float v = pend0Value_.load();
            char buf[24];
            if (engineGet(g_pspecs[0].key, buf, sizeof buf) && std::atoi(buf) != (int)std::lround(v)) sendValue(0, v);
            told_[0] = -1.0e9f;   // read back below
            hostMoved_[0].store(true);
        }
        for (int i = 0; i < kNumParams; ++i)
            if (release_[i].exchange(false)) { held_[i].store(false); pushValue(i, 0.0f); }
        char buf0[32];
        {   // a favourite picked in the MPC's PRESET menu (not the re-pick that follows a project load: the project's sound wins)
            // As in 0.2.11, the current program is the engine's "favourite": the picked slot while it is the sound, else the first empty
            // slot, so picking any stored favourite is a change. The worker follows the engine; a host pick differs from what it was told.
            const int prog = currentProgram();
            if (prog != lastProgram_)
            {
                lastProgram_ = prog;
                // before the boot, the MPC's pick on insert (program 0) is not a choice: the engine could not load it, yet it would show it
                if (now >= ignoreProgUntil_.load() && engineReady()) { char v[16]; std::snprintf(v, sizeof v, "%d", prog); engineSet("favourite", v); }
            }
            else if (engineGet("favourite", buf0, sizeof buf0))
            {
                const int f = std::atoi(buf0);
                if (f >= 0 && f < kFavSlots && f != prog) { currentProgram_ = f; lastProgram_ = f; wantDisplay_ = true; }
            }
        }
        if (kbDirty_.exchange(false))   // the keyboard opened or closed, or the typed name changed
        {
            pushValue(kKbOpen, kbOpen_.load() ? 1.0f : 0.0f);
            counter_ = (counter_ + 1) % 1024;
            pushValue(kFavName, (float)counter_);
            wantDisplay_ = true;
        }
        if (force || tick_ % 25 == 0) refreshFavNames();   // +FAV / -FAV (or another instance) changed the list: new names in the PRESET menu
        if (notifyUi_.exchange(false)) { t_pushing = kUiParam; notifyHostParameterChanged(kUiParam); t_pushing = -1; }
        if (resync_.exchange(false))
        {
            for (int i = 0; i < kNumParams; ++i) { told_[i].store(-1.0e9f); hostMoved_[i].store(true); }
            std::fill(textHash_.begin(), textHash_.end(), 0u);
        }

        // display_rev moves on anything that changes many values (sound, bank, state, PLAY target, the BANKS page): then every value and
        // tile is read back
        char buf[128];
        bool full = force;
        if (engineGet("display_rev", buf, sizeof buf))
        {
            const uint32_t r = fnv(buf) | 1u;
            if (r != lastRev_) { lastRev_ = r; full = true; }
        }
        int changed = 0;
        for (int i = 0; i < kNumParams; ++i)   // the engine's keys: the released ones and those appended after the favourite keys
        {
            const PSpec& s = g_pspecs[i];
            if (s.flags & (kUi | kReserved | kLocal)) continue;
            const bool moved = hostMoved_[i].exchange(false);
            if (!(moved || full)) continue;
            if (s.flags & kTile)
            {
                char k2[64];
                std::snprintf(k2, sizeof k2, "%s_on", s.key);
                const float on = engineGet(k2, buf, sizeof buf) && std::atoi(buf) ? 1.0f : 0.0f;
                if (on < 0.5f) held_[i].store(false);   // dark: the host sends no 0 for a tile the engine turned off, so its next tap must fire
                if (moved || on != told_[i]) { pushValue(i, on); if (!moved) ++changed; }
                continue;
            }
            if (!(s.flags & kPolled)) continue;
            if (i == 0 && pend0At_.load()) { if (moved) hostMoved_[0].store(true); continue; }
            // while the host is still moving it, don't send the engine's value back under the finger; read it back once it has rested
            if (!force && now - hostAt_[i].load() < 300) { if (moved || full) hostMoved_[i].store(true); continue; }
            if (!engineGet(s.key, buf, sizeof buf)) continue;
            float v = (float)std::atof(buf);
            if ((s.flags & kChoice) && !(buf[0] == '-' || (buf[0] >= '0' && buf[0] <= '9')))   // an option answered by its label (rom_bc: "Yes")
                for (int k = 0; k < s.nchoices; ++k)
                    if (!std::strcmp(buf, s.choices[k])) { v = (float)k; break; }
            v = std::min(std::max(v, s.min), s.max);
            if (i == kRomBc)   // engine-owned: told when the engine's value changes (the ROM booted or switched), not on every re-read, so
            {                  // a project's saved value stands until the engine says otherwise
                if (v != romBcSeen_ || romBcUndo_.exchange(false)) { romBcSeen_ = v; pushValue(i, v); }
                continue;
            }
            if (moved || v != told_[i]) { pushValue(i, v); if (!moved) ++changed; }
        }

        // text readouts: every 100 ms; a changed text bumps the counter (the host re-reads text when the value moves)
        bool textChanged = false;
        if (force || full || tick_ % 10 == 0)
            for (int i = 0; i < kNumParams; ++i)
            {
                const PSpec& s = g_pspecs[i];
                if (!(s.flags & kText) || (s.flags & (kUi | kReserved | kLocal))) continue;
                const uint32_t h = engineGet(s.key, buf, sizeof buf) ? fnv(buf) | 1u : 1u;
                if (h == textHash_[(size_t)i]) continue;
                textHash_[(size_t)i] = h;
                textChanged = true;
                if (s.flags & kTile) continue;   // a tile's value is its lit state
                counter_ = (counter_ + 1) % 1024;
                pushValue(i, (float)counter_);
            }
        // Many values at once or new text: one display update, at most every 100 ms. Never periodically: it re-lists programs and
        // closes the PRESET menu.
        if (textChanged || changed > 8) wantDisplay_ = true;
        if (wantDisplay_ && (force || now - lastDisplay_ >= 100))
        {
            wantDisplay_ = false;
            lastDisplay_ = now;
            requestDisplayUpdate();
        }
    }

    // ---- favourites: the engine's slots, named "fav_name:<n>" ("-" when empty), re-read when the list changes ("fav_gen").
    // Not "favourite:<n>": that read holds the CPU / dropout readout for 15 s (it is for the MPC's PRESET menu), and a read every
    // pass would freeze it for good (SDK-PORTING.md, Vavra lessons).
    void refreshFavNames()   // worker thread
    {
        char b[64], k[32];
        if (!engineGet("fav_gen", b, sizeof b)) return;
        const long gen = std::atol(b);
        if (gen == favGen_) return;
        favGen_ = gen;
        bool any = false;
        for (int i = 0; i < kFavSlots; ++i)
        {
            std::snprintf(k, sizeof k, "fav_name:%d", i);
            if (!engineGet(k, b, sizeof b)) continue;
            const std::string nm = std::to_string(i + 1) + " " + (std::strcmp(b, "-") ? std::string(b) : std::string("--"));
            if (programs_[(size_t)i].name != nm) { programs_[(size_t)i].name = nm; any = true; }
        }
        if (any) wantDisplay_ = true;
    }

public:
#ifdef OSIRUS_TEST
    void dbgTick() { tickOnce(true); }
    bool dbgReady() { return engineReady(); }
    std::string dbgEngine(const char* key)
    {
        char b[kStateMax];
        return engineGet(key, b, sizeof b) ? std::string(b) : std::string();
    }
    void dbgEngineSet(const char* key, const char* v) { engineSet(key, v); }
#endif

private:
    const mpc_engine_t* eng_ = nullptr;
    void* inst_ = nullptr;
    std::string dataDir_;
    std::thread worker_;
    std::atomic<bool> quit_{false};
    std::atomic<bool> resync_{true}, notifyUi_{false};
    std::atomic<long long> pend0At_{0};
    std::atomic<float> pend0Value_{0.0f};
    std::atomic<bool>* held_ = nullptr;
    std::mutex kbMu_;
    std::string kbName_;                       // the name being typed on the keyboard
    bool kbShift_ = false;
    std::atomic<bool> kbOpen_{false}, kbDirty_{false};
    std::vector<long long> lastFire_ = std::vector<long long>((size_t)kNumParams, 0);
    std::atomic<bool>* release_ = nullptr;
    std::atomic<bool>* hostMoved_ = nullptr;   // read this one back and tell the host on the next pass
    std::atomic<long long>* hostAt_ = nullptr; // when the host last moved it (ms), per parameter
    std::atomic<float>* told_ = nullptr;       // the value the host was last told (or sent), per parameter
    std::vector<float> lastPos_;               // the host's last position, for settle()
    std::vector<uint32_t> textHash_;
    std::mutex stateMu_;
    std::string pendingState_;                 // a project's state given before the engine booted
    std::atomic<long long> ignoreProgUntil_{0};
    int lastProgram_ = 0;   // worker thread
    float romBcSeen_ = -1.0f;   // worker thread: the engine's rom_bc last read
    std::atomic<bool> romBcUndo_{false};   // the host wrote rom_bc: put the engine's value back
    long favGen_ = -1;      // worker thread: the engine's fav_gen the names were read at
    // audio thread: resampler
    double step_ = 1.0, frac_ = 0;
    int have_ = 0, srcPos_ = 0, srcLen_ = 0;
    float src_[4] = {0, 0, 0, 0};
    int16_t pcm_[kChunk * 2] = {0};
    uint32_t lastRev_ = 0;
    int counter_ = 0;
    long tick_ = 0;
    bool wantDisplay_ = false;
    long long lastDisplay_ = 0;
};

// The same entry as MPC_PLUGIN_ENTRY, plus a wrapped effSetChunk: an "MPCP" chunk loads with engine writes held back (the engine
// state in its extra part is the truth); a 1.x chunk (the engine's state JSON) goes to the engine as before.
namespace {
VstIntPtr (*g_origDispatcher)(AEffect*, VstInt32, VstInt32, VstIntPtr, void*, float) = nullptr;

VstIntPtr osDispatcher(AEffect* e, VstInt32 opcode, VstInt32 index, VstIntPtr value, void* ptr, float opt)
{
    if (opcode == effSetChunk && e->object && ptr && value > 0)
    {
        OsirusPlugin* p = static_cast<OsirusPlugin*>(e->object);
        if (value >= 4 && std::memcmp(ptr, "MPCP", 4) == 0)
        {
            p->loading_.store(true);
            const VstIntPtr r = g_origDispatcher(e, opcode, index, value, ptr, opt);
            p->loading_.store(false);
            p->requestResync();
            return r;
        }
        return p->loadLegacy(static_cast<const char*>(ptr), (size_t)value) ? 1 : 0;
    }
    return g_origDispatcher(e, opcode, index, value, ptr, opt);
}
} // namespace

#ifdef OSIRUS_TEST   // offline test hooks (tests/host_test.cpp); absent from the release build
extern "C" MPC_EXPORT void os_dbg_tick(AEffect* e) { static_cast<OsirusPlugin*>(e->object)->dbgTick(); }
extern "C" MPC_EXPORT int os_dbg_ready(AEffect* e) { return static_cast<OsirusPlugin*>(e->object)->dbgReady() ? 1 : 0; }
extern "C" MPC_EXPORT int os_dbg_engine(AEffect* e, const char* key, char* out, int n)
{
    const std::string s = static_cast<OsirusPlugin*>(e->object)->dbgEngine(key);
    std::snprintf(out, (size_t)n, "%s", s.c_str());
    return (int)s.size();
}
extern "C" MPC_EXPORT void os_dbg_engine_set(AEffect* e, const char* key, const char* v) { static_cast<OsirusPlugin*>(e->object)->dbgEngineSet(key, v); }
#endif

extern "C" MPC_EXPORT AEffect* VSTPluginMain(audioMasterCallback host)
{
    if (host != nullptr && host(nullptr, audioMasterVersion, 0, 0, nullptr, 0.0f) == 0) return nullptr;   // host is VST1 only
    AEffect* e = mpc::detail::createEffect(new OsirusPlugin(), host);
    if (e && !g_origDispatcher) g_origDispatcher = e->dispatcher;
    if (e) e->dispatcher = osDispatcher;
    return e;
}
extern "C" MPC_EXPORT int os_dbg_kb_open(AEffect* e) { return static_cast<OsirusPlugin*>(e->object)->dbgKbOpen() ? 1 : 0; }
extern "C" MPC_EXPORT int os_dbg_kb_name(AEffect* e, char* out, int n)
{
    const std::string s = static_cast<OsirusPlugin*>(e->object)->dbgKbName();
    std::snprintf(out, (size_t)n, "%s", s.c_str());
    return 1;
}

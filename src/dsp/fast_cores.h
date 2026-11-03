/* fast_cores.h: put an engine's heavy threads on the fast cores of a big.LITTLE CPU, safely beside MPC's audio threads.
 *
 * MPC Live III (Gen2): cores 0-3 are Cortex-A55 at 1.8 GHz, cores 4-7 Cortex-A76 at 2.4 GHz. The A76 does ~3x the work per
 * thread (measured 2026-11-03: Osirus 91% -> 31% of a core, Xenia 190 -> 62, JV-880 56 -> 22, Machinemodule 76 -> 27, MS2KR
 * dropouts gone). MPC pins its SCHED_RR audio threads (rt priority 20) to cores 4-7, "Audio Processing" on 7, MIDI/FileIO
 * on 3. Left alone, Linux spreads a plugin's threads over all cores, slow ones included; "least busy core" pickers choose
 * the slow ones (MPC keeps the fast ones busy). docs/EMULATOR_PORTS.md has the measurements and the rest.
 *
 *   fastcores::pin_this_thread()   this thread (and every thread it creates afterwards) -> the fast cores minus the last;
 *                                  returns false and changes nothing on a CPU whose cores are all the same speed (Force, MPC Gen1)
 *   fastcores::rt_priority(p)      a SCHED_FIFO priority that stays BELOW MPC's audio threads when on the fast cores (cap 15);
 *                                  p unchanged on same-speed CPUs, where the port's tuned value stays as it was
 *   fastcores::usable()            the core list itself (e.g. to spread several worker threads one per core)
 *   fastcores::pin_named(name, i)  every thread of this process called <name> -> fast core i (modulo the count); for threads a
 *                                  library starts itself (gearmulator's "DSP", "MC68331"). Threads that hand work to each other
 *                                  all the time (a CPU and its DSP) run best on a core each: sharing one mask, they often shared
 *                                  a core (MS2KR in MPC 2026-11-03: 113 dropouts -> 8-14 once on separate cores).
 *   fastcores::pin_this_to(i)      this thread -> fast core i
 * Header-only C++; C ports: copy the three functions. Call from the thread itself, before it starts its own workers. */
#pragma once
#include <sched.h>
#include <dirent.h>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <vector>

namespace fastcores {

// The fastest cores by cpuinfo_max_freq, without the highest-numbered one when three or more (MPC's "Audio Processing"
// lives there). Empty when every core has the same top speed, or the information is missing.
inline std::vector<int> usable()
{
    long f[64]; int n = 0; long best = 0;
    for (; n < 64; ++n) {
        char p[96]; std::snprintf(p, sizeof p, "/sys/devices/system/cpu/cpu%d/cpufreq/cpuinfo_max_freq", n);
        std::FILE* fp = std::fopen(p, "r");
        if (!fp) break;
        if (std::fscanf(fp, "%ld", &f[n]) != 1) f[n] = 0;
        std::fclose(fp);
        if (f[n] > best) best = f[n];
    }
    std::vector<int> fast; bool mixed = false;
    for (int i = 0; i < n; ++i) { if (f[i] == best) fast.push_back(i); else mixed = true; }
    if (!mixed) return {};
    if (fast.size() >= 3) fast.pop_back();
    return fast;
}

inline bool pin_this_thread()
{
    const auto fast = usable();
    if (fast.empty()) return false;
    cpu_set_t set; CPU_ZERO(&set);
    for (int c : fast) CPU_SET(c, &set);
    return sched_setaffinity(0, sizeof set, &set) == 0;
}

inline bool pin_tid(int tid, int core)
{
    cpu_set_t set; CPU_ZERO(&set); CPU_SET(core, &set);
    return sched_setaffinity(tid, sizeof set, &set) == 0;
}

inline bool pin_this_to(int i)
{
    const auto fast = usable();
    return !fast.empty() && pin_tid(0, fast[static_cast<size_t>(i) % fast.size()]);
}

// Returns how many threads it moved; 0 on same-speed CPUs.
inline int pin_named(const char* name, int i)
{
    const auto fast = usable();
    if (fast.empty()) return 0;
    const int core = fast[static_cast<size_t>(i) % fast.size()];
    int n = 0;
    if (DIR* d = opendir("/proc/self/task")) {
        while (dirent* e = readdir(d)) {
            if (e->d_name[0] == '.') continue;
            char p[64], comm[32] = {};
            std::snprintf(p, sizeof p, "/proc/self/task/%s/comm", e->d_name);
            if (std::FILE* f = std::fopen(p, "r")) {
                if (std::fgets(comm, sizeof comm, f)) comm[std::strcspn(comm, "\n")] = 0;
                std::fclose(f);
            }
            if (std::strcmp(comm, name) == 0 && pin_tid(std::atoi(e->d_name), core)) ++n;
        }
        closedir(d);
    }
    return n;
}

// MPC's audio threads are SCHED_RR priority 20 on the fast cores: a plugin thread there must stay below, or it preempts
// MPC's own audio engine. 15 keeps it above every normal thread and MPC's MIDI threads (10).
inline int rt_priority(int wanted) { return usable().empty() ? wanted : (wanted > 15 ? 15 : wanted); }

}  // namespace fastcores

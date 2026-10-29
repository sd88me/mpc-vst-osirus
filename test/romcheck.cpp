// ROM checker: says which files in a folder the plugin will accept as a Virus ROM, using the engine's own recognition
// (virusLib::ROMLoader), so it cannot disagree with what the plugin does at load time.
// usage: osirus_romcheck [--json] <folder>      exit 0 = at least one Virus ROM recognised, 1 = none, 2 = usage / unreadable
#include "virusLib/romloader.h"
#include "virusLib/romfile.h"

#include <algorithm>
#include <cstdio>
#include <cstring>
#include <dirent.h>
#include <string>
#include <sys/stat.h>
#include <unistd.h>
#include <vector>

struct Entry { std::string name; long size; std::string verdict; std::string model; };

static std::string base(const std::string &p) { size_t s = p.find_last_of("/\\"); return s == std::string::npos ? p : p.substr(s + 1); }

static std::string json_str(const std::string &s) {
    std::string o = "\"";
    for (char c : s) { if (c == '"' || c == '\\') o += '\\'; o += (unsigned char)c < 0x20 ? ' ' : c; }
    return o + "\"";
}

int main(int argc, char **argv)
{
    bool json = false; const char *dir = nullptr;
    for (int k = 1; k < argc; k++) { if (!strcmp(argv[k], "--json")) json = true; else dir = argv[k]; }
    if (!dir) { fprintf(stderr, "usage: %s [--json] <roms folder>\n", argv[0]); return 2; }

    DIR *d = opendir(dir);
    if (!d) { fprintf(stderr, "cannot open %s\n", dir); return 2; }
    std::vector<Entry> files;
    while (const dirent *e = readdir(d)) {
        if (e->d_name[0] == '.') continue;
        struct stat st;
        std::string path = std::string(dir) + "/" + e->d_name;
        if (stat(path.c_str(), &st) != 0 || !S_ISREG(st.st_mode)) continue;
        files.push_back({e->d_name, (long)st.st_size, "", ""});
    }
    closedir(d);
    std::sort(files.begin(), files.end(), [](const Entry &a, const Entry &b) { return a.name < b.name; });

    // the same call the plugin makes at load; a ROM built from a .mid pair names the OS file it came from
    // the library prints its boot-ROM details on stdout: park stdout on stderr while it reads, so --json stays clean
    fflush(stdout);
    const int out = dup(1); dup2(2, 1);
    auto roms = virusLib::ROMLoader::findROMs(std::string(dir));
    fflush(stdout); dup2(out, 1); close(out);
    std::vector<std::pair<std::string, std::string>> found;     // file name -> model
    for (auto &r : roms) found.push_back({base(r.getFilename()), r.getModelName()});

    for (auto &f : files) {
        for (auto &m : found) if (m.first == f.name) { f.verdict = "ok"; f.model = m.second; }
        if (!f.verdict.empty()) continue;
        std::string ext = f.name.size() > 4 ? f.name.substr(f.name.size() - 4) : "";
        std::transform(ext.begin(), ext.end(), ext.begin(), ::tolower);
        if (ext == ".mid" && f.size >= 500 * 1024 && f.size <= 600 * 1024) { f.verdict = "companion"; }   // a presets dump: only used next to a Virus A OS file
        else if (ext == ".txt" || ext == ".md") f.verdict = "ignored";
        else if (ext == ".bin" && f.size != 512 * 1024) f.verdict = "wrong size (a Virus ROM .bin is exactly 524288 bytes)";
        else if (ext == ".bin" || ext == ".mid") f.verdict = "not recognised as a Virus A, B or C ROM";
        else f.verdict = "ignored (not .bin or .mid)";
    }

    bool any = !found.empty();
    if (json) {
        printf("{\"ok\":%s,\"roms\":[", any ? "true" : "false");
        for (size_t k = 0; k < found.size(); k++) printf("%s{\"file\":%s,\"model\":%s}", k ? "," : "", json_str(found[k].first).c_str(), json_str(found[k].second).c_str());
        printf("],\"files\":[");
        for (size_t k = 0; k < files.size(); k++)
            printf("%s{\"file\":%s,\"size\":%ld,\"verdict\":%s}", k ? "," : "", json_str(files[k].name).c_str(), files[k].size, json_str(files[k].verdict).c_str());
        printf("]}\n");
    } else {
        for (auto &f : files)
            printf("%-8s %-50s %9ld  %s%s\n", f.verdict == "ok" ? "OK" : (f.verdict == "companion" ? "ok" : "--"), f.name.c_str(), f.size,
                   f.verdict == "ok" ? "Virus " : "", f.verdict == "ok" ? f.model.c_str() : f.verdict.c_str());
        if (files.empty()) printf("%s is empty\n", dir);
        if (any) printf("%zu Virus ROM(s) recognised\n", found.size());
        else printf("no Virus ROM recognised in %s\n", dir);
    }
    return any ? 0 : 1;
}

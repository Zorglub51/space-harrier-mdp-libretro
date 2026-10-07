// license:GPL-2.0-or-later
#pragma once

#include <atomic>
#include <cstddef>
#include <cstdint>
#include <cstring>
#include <string>

namespace sh_mdp_explosions {

// Configuration is captured before starting the machine. A runtime option
// change creates a fresh machine; executable ROM is never edited while running.
inline bool requested = false;
inline std::string system_directory;
inline std::atomic<bool> active{false};
inline std::atomic<bool> eligible{false};
// Only option-triggered restarts skip automatic/command-line state loading.
// Ordinary content loads retain the frontend's normal save settings.
inline std::atomic<bool> restart_from_beginning{false};
enum class result { none, applied, missing_donor, invalid_donor, rejected_patch, original_restored, reload_failed };
inline std::atomic<result> notification{result::none};

inline constexpr char donor_filename[] = "jp_jp_space_harrier.smp";
inline constexpr std::size_t donor_size = 0x3e0000;
inline constexpr char donor_sha1[] = "e87e9338d7842db68a7a1e77bd5fc5b2bc8b2b72";

// Original-mode Libretro states retain their existing format. Modded states
// carry a versioned prefix so pointers into injected ROM cannot be restored
// into a machine running the original game (or vice versa).
inline constexpr std::uint8_t state_tag[16] = {
    'S', 'H', '2', 'E', 'X', 'P', 'L', '0', 3, 0, 0, 0, 0, 0, 0, 0
};

inline bool state_matches(const void *data, std::size_t size, bool mod_active)
{
    if (!data)
        return false;
    const bool tagged = size >= 8 && std::memcmp(data, state_tag, 8) == 0;
    return mod_active
        ? tagged && size >= sizeof(state_tag) && std::memcmp(data, state_tag, sizeof(state_tag)) == 0
        : !tagged;
}

inline const char *message(result value)
{
    switch (value)
    {
    case result::applied:
        return "SH2: SH1 explosions enabled for all exploding objects.";
    case result::missing_donor:
        return "SH2: original explosions retained. Put jp_jp_space_harrier.smp beside SH2 or in the system folder, then restart content.";
    case result::invalid_donor:
        return "SH2: original explosions retained. The SH1 donor ROM is unreadable or not the supported original version.";
    case result::rejected_patch:
        return "SH2: original explosions retained. The optional ROM patch could not be applied safely.";
    case result::original_restored:
        return "SH2: original explosions restored. Game restarted.";
    case result::reload_failed:
        return "SH2: content restart failed. Close and reload the ROM.";
    default:
        return nullptr;
    }
}

} // namespace sh_mdp_explosions

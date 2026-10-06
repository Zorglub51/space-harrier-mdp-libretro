// license:GPL-2.0-or-later
#pragma once

#include "sh2_explosion_options.h"
#include "sh2_explosion_patch.h"
#include "util/corefile.h"
#include "util/hashing.h"

#include <array>
#include <vector>

namespace sh_mdp_explosions {

inline std::string donor_next_to(const char *content_path)
{
    const std::string path = content_path ? content_path : "";
    const std::size_t slash = path.find_last_of("/\\");
    return (slash == std::string::npos ? std::string() : path.substr(0, slash + 1)) + donor_filename;
}

inline void apply(std::uint8_t *rom, std::size_t image_size, std::size_t capacity,
                  bool recognized_sh2, const char *content_path)
{
    eligible = recognized_sh2 && image_size == 0x380000;
    if (!requested || !eligible)
        return;

    const std::array<std::string, 2> candidates = {
        donor_next_to(content_path),
        system_directory.empty() ? std::string() : system_directory + "/" + donor_filename
    };
    result failure = result::missing_donor;
    for (std::size_t index = 0; index < candidates.size(); ++index)
    {
        const std::string &path = candidates[index];
        if (path.empty() || (index && path == candidates[0]))
            continue;
        util::core_file::ptr file;
        if (util::core_file::open(path, OPEN_FLAG_READ, file))
            continue;
        failure = result::invalid_donor;
        std::uint64_t length = 0;
        if (file->length(length) || length != donor_size)
            continue;
        std::vector<std::uint8_t> donor(donor_size);
        const auto read = util::read(*file, donor.data(), donor.size());
        if (read.first || read.second != donor.size() ||
            util::sha1_creator::simple(donor.data(), donor.size()).as_string() != donor_sha1)
            continue;

        // Build transactionally: even a rejected late validation must leave
        // every original byte and padding byte unchanged.
        std::vector<std::uint8_t> patched(rom, rom + capacity);
        if (!markv::apply_sh2_enemy_explosions(patched.data(), capacity, donor.data(), donor.size()))
        {
            notification = result::rejected_patch;
            return;
        }
        std::memcpy(rom, patched.data(), capacity);
        active = true;
        notification = result::applied;
        return;
    }
    notification = failure;
}

} // namespace sh_mdp_explosions

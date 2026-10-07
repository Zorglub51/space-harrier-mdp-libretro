// license:GPL-2.0-or-later
#pragma once
#include <atomic>
namespace sh_mdp_video {
// The native path stays the default; Mark VI adds host-side presentation work.
inline std::atomic<bool> markvi{false};
}

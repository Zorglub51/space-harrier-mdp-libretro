#!/bin/bash
set -euo pipefail

package_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
retroarch="${SH_MDP_RETROARCH:-/Applications/RetroArch.app/Contents/MacOS/RetroArch}"
core="${package_dir}/shmdp_libretro.dylib"
rom="${1:-}"
if [[ -z "${rom}" && -f "${package_dir}/rom-path.txt" ]]; then
    IFS= read -r rom < "${package_dir}/rom-path.txt"
fi

fail() {
    echo "Erreur : $*" >&2
    echo "Appuyez sur Entrée pour fermer."
    read -r || true
    exit 1
}

[[ "$(uname -m)" == arm64 ]] || fail "Ce paquet nécessite un Mac Apple Silicon."
[[ -x "${retroarch}" ]] || fail "RetroArch est introuvable dans Applications."
[[ -f "${core}" ]] || fail "Le cœur manque dans ce dossier."
[[ -f "${rom}" ]] || fail "Indiquez le chemin de votre ROM SH1 originale dans rom-path.txt."
rom_sha="$(/usr/bin/shasum "${rom}")"
[[ "${rom_sha%% *}" == e87e9338d7842db68a7a1e77bd5fc5b2bc8b2b72 ]] || fail "La ROM n'est pas l'original SH1 attendu."
(cd "${package_dir}" && /usr/bin/shasum -a 256 -c CORE_SHA256.txt) || fail "Le cœur ne correspond pas au paquet vérifié."

session="${package_dir}/session"
mkdir -p "${session}"/{saves,states,screenshots,system,logs,config}
retroarch_data="${HOME}/Library/Application Support/RetroArch"
cat > "${session}/retroarch.cfg" <<EOF
config_save_on_exit = "false"
video_driver = "vulkan"
audio_driver = "coreaudio3"
input_driver = "cocoa"
input_joypad_driver = "mfi"
menu_driver = "ozone"
video_fullscreen = "false"
video_windowed_fullscreen = "false"
video_scale = "3"
video_vsync = "true"
audio_sync = "true"
video_shader_enable = "false"
video_smooth = "false"
pause_nonactive = "true"
pause_on_disconnect = "false"
rewind_enable = "false"
run_ahead_enabled = "false"
preemptive_frames_enable = "false"
savestate_auto_load = "false"
savestate_auto_save = "false"
auto_overrides_enable = "false"
auto_remaps_enable = "false"
auto_shaders_enable = "false"
history_list_enable = "false"
content_runtime_log = "false"
content_runtime_log_aggregate = "false"
core_info_cache_enable = "false"
global_core_options = "true"
savefile_directory = "${session}/saves"
savestate_directory = "${session}/states"
screenshot_directory = "${session}/screenshots"
system_directory = "${session}/system"
log_dir = "${session}/logs"
rgui_config_directory = "${session}/config"
core_options_path = "${session}/core-options.cfg"
libretro_info_path = "${package_dir}"
assets_directory = "${retroarch_data}/assets"
joypad_autoconfig_dir = "${retroarch_data}/autoconfig"
input_player1_up = "up"
input_player1_down = "down"
input_player1_left = "left"
input_player1_right = "right"
input_player1_b = "z"
input_player1_a = "x"
input_player1_start = "enter"
input_libretro_device_p1 = "1"
input_menu_toggle = "f1"
input_pause_toggle = "p"
input_screenshot = "f8"
input_exit_emulator = "escape"
quit_press_twice = "false"
EOF
cat > "${session}/core-options.cfg" <<'EOF'
mame_cheats_enable = "disabled"
mame_auto_save = "disabled"
mame_read_config = "disabled"
mame_write_config = "disabled"
mame_mame_paths_enable = "disabled"
mame_mame_4way_enable = "disabled"
mame_throttle = "disabled"
mame_cpu_overclock = "default"
mame_thread_mode = "enabled"
EOF

unset MDP_SPRITE_PERSIST
log="${session}/logs/sh1-$(date '+%Y%m%d-%H%M%S')-$$.log"
echo "SH1 — essai du cœur corrigé"
echo "Entrée : démarrer | Flèches : bouger | Z : tirer"
echo "P : pause | F8 : capture | Échap : quitter"
echo "Journal : ${log}"
cd "${session}"
exec /usr/bin/arch -arm64 "${retroarch}" \
    --config "${session}/retroarch.cfg" --verbose --log-file "${log}" \
    -L "${core}" "${rom}"

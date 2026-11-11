#include "machine.hpp"
#include "interpolation.hpp"

#include <charconv>
#include <cstdio>
#include <exception>
#include <memory>
#include <string_view>
#ifdef _WIN32
#define WIN32_LEAN_AND_MEAN
#ifndef NOMINMAX
#define NOMINMAX
#endif
#include <windows.h>
#include <string>
#endif

// The public libretro ABI uses C names and these data layouts.
// https://raw.githubusercontent.com/libretro/libretro-common/master/include/libretro.h
extern "C" {

struct retro_game_info {
    const char *path;
    const void *data;
    std::size_t size;
    const char *meta;
};

struct retro_system_info {
    const char *library_name, *library_version, *valid_extensions;
    bool need_fullpath, block_extract;
};

struct retro_game_geometry {
    unsigned base_width, base_height, max_width, max_height;
    float aspect_ratio;
};

struct retro_system_av_info {
    retro_game_geometry geometry;
    struct {
        double fps, sample_rate;
    } timing;
};

struct retro_message {
    const char *msg;
    unsigned frames;
};

struct retro_input_descriptor {
    unsigned port, device, index, id;
    const char *description;
};

struct retro_variable {
    const char *key, *value;
};

using Environment = bool (*)(unsigned, void *);
using VideoCallback = void (*)(const void *, unsigned, unsigned, std::size_t);
using AudioSample = void (*)(std::int16_t, std::int16_t);
using AudioBatch = std::size_t (*)(const std::int16_t *, std::size_t);
using InputPoll = void (*)();
using InputState = std::int16_t (*)(unsigned, unsigned, unsigned, unsigned);

}

namespace {

using namespace markv;

constexpr unsigned set_message = 6, set_pixel_format = 10, set_input_descriptors = 11, joypad = 1;
constexpr unsigned get_variable = 15, set_variables = 16, get_variable_update = 17;
constexpr unsigned set_system_av_info = 32, set_geometry = 37;
#if MARKV_DESKTOP_120
constexpr unsigned get_target_refresh_rate = 50 | 0x10000;
#endif
constexpr int xrgb8888 = 1, rgb565 = 2;
constexpr std::array<std::int16_t, 2 * (ticks_per_frame / ticks_per_sample)> silence{};
constexpr std::array<unsigned, 8> buttons{4, 5, 6, 7, 0, 8, 9, 3};
retro_variable options[] = {
    {"markv_fm_level", "FM Level; 100%|75%|50%|25%|0%"},
    {"markv_pcm_level", "PCM Level; 100%|75%|50%|25%|0%"},
    {"markv_psg_level", "PSG Level; 100%|75%|50%|25%|0%"},
    {"markv_widescreen", "Widescreen (16:9); Disabled|Enabled"},
    {"markv_mark_vi", "Mark VI; Disabled|Enabled"},
#if MARKV_DESKTOP_120
    {"markv_120_hz", "120 Hz; Disabled|Enabled"},
#endif
    {},
};
retro_input_descriptor inputs[] = {
    {0, joypad, 0, buttons[0], "Up"},
    {0, joypad, 0, buttons[1], "Down"},
    {0, joypad, 0, buttons[2], "Left"},
    {0, joypad, 0, buttons[3], "Right"},
    {0, joypad, 0, buttons[4], "B"},
    {0, joypad, 0, buttons[5], "C"},
    {0, joypad, 0, buttons[6], "A"},
    {0, joypad, 0, buttons[7], "Start"},
    {},
};

Environment environment;
VideoCallback video_callback;
AudioSample audio_sample;
AudioBatch audio_batch;
InputPoll input_poll;
InputState input_state;
struct Preferences {
    AudioLevels levels;
    bool wide = false, mark_vi = false, double_rate = false;
};
struct Game {
    std::vector<Byte> cartridge;
    std::unique_ptr<Machine> machine;
    std::unique_ptr<FrameInterpolation> interpolation;
    Preferences requested;
    bool double_rate_requested = false, second_half = false;
};
// Match the frontend's unload lifecycle, including when it calls dlclose().
Game *game_session = nullptr;
std::array<Word, wide_width * screen_height> packed_video;
bool use_565 = false, halted = false;
unsigned controller = joypad;

std::string_view option(const char *key)
{
    retro_variable value{key, nullptr};
    return environment(get_variable, &value) && value.value ? value.value : "";
}

unsigned level(const char *key)
{
    const auto text = option(key);
    if (text.size() < 2 || text.back() != '%')
        return 100;
    unsigned value = 0;
    const char *last = text.data() + text.size() - 1;
    const auto parsed = std::from_chars(text.data(), last, value);
    return parsed.ec == std::errc{} && parsed.ptr == last && value <= 100 ? value : 100;
}

retro_game_geometry geometry(bool wide)
{
    return {wide ? wide_width : screen_width, screen_height, wide_width, screen_height,
            wide ? 16.0f / 9.0f : 4.0f / 3.0f};
}

retro_system_av_info av_info(bool wide, bool double_rate)
{
    return {geometry(wide), {frame_rate * (double_rate ? 2 : 1), sample_rate}};
}

void notify(const char *message);

void apply_options(Game &game, bool initial)
{
    auto &bus = game.machine->bus;
    Preferences requested;
    requested.levels = {level("markv_fm_level"), level("markv_pcm_level"), level("markv_psg_level")};
    if (bus.supports_video_options()) {
        requested.wide = option("markv_widescreen") == "Enabled";
        requested.mark_vi = option("markv_mark_vi") == "Enabled";
    }
#if MARKV_DESKTOP_120
    requested.double_rate = option("markv_120_hz") == "Enabled";
#endif
    bool double_rate = requested.double_rate;
#if MARKV_DESKTOP_120
    float target_hz = 0;
    if (double_rate && environment(get_target_refresh_rate, &target_hz) &&
        target_hz > 0 && target_hz < 2 * frame_rate - 1) {
        double_rate = false;
        if (initial || !game.requested.double_rate || game.double_rate_requested)
            notify("Mark V: using native speed. Set RetroArch's output refresh rate to 120 Hz to enable interpolation.");
    }
#endif
    bool wide = bus.widescreen();
    if (initial) {
        wide = requested.wide;
        if (double_rate)
            game.interpolation = std::make_unique<FrameInterpolation>();
    } else {
        if (double_rate != game.double_rate_requested && double_rate != bool(game.interpolation)) {
            auto timing = av_info(requested.wide, double_rate);
            try {
                auto next = double_rate ? std::make_unique<FrameInterpolation>() : nullptr;
                if (environment(set_system_av_info, &timing)) {
                    game.interpolation = std::move(next);
                    wide = requested.wide;
                } else {
                    notify("Mark V: the frontend declined the refresh rate change.");
                }
            } catch (const std::bad_alloc &) {
                notify("Mark V: could not allocate the intermediate frame.");
            }
        }
        if (requested.wide != game.requested.wide && requested.wide != wide) {
            auto dimensions = geometry(requested.wide);
            if (environment(set_geometry, &dimensions))
                wide = requested.wide;
        }
    }
    bus.set_video_options(wide, requested.mark_vi);
    bus.set_audio_levels(requested.levels);
    game.requested = requested;
    game.double_rate_requested = double_rate;
}

void notify(const char *message)
{
    std::fprintf(stderr, "%s\n", message);
    if (environment) {
        retro_message notice{message, 360};
        environment(set_message, &notice);
    }
}

void run_machine()
{
    auto &machine = *game_session->machine;
    Byte pad = 0xff;
    if (controller == joypad && input_state) {
        for (unsigned i = 0; i < buttons.size(); ++i)
            if (input_state(0, joypad, 0, buttons[i]))
                pad &= ~(1u << i);
    }
    machine.bus.buttons(pad);
    try {
        machine.frame(game_session->interpolation.get());
    } catch (const CpuFault &fault) {
        char message[128];
        std::snprintf(message, sizeof(message), "Mark V 68000 fault at $%06x, opcode $%04x, frame %llu",
                      unsigned(fault.pc), unsigned(fault.opcode), static_cast<unsigned long long>(machine.frames));
        notify(message);
        halted = true;
    } catch (const Z80Fault &fault) {
        char message[128];
        std::snprintf(message, sizeof(message), "Mark V Z80 fault at $%04x, opcode $%02x, frame %llu",
                      unsigned(fault.pc), unsigned(fault.opcode), static_cast<unsigned long long>(machine.frames));
        notify(message);
        halted = true;
    }
}

void present(Game &game, bool second)
{
    const unsigned width = game.machine->video_width();
    if (video_callback) {
        const auto pixels = game.interpolation && !second && !halted ?
            game.interpolation->frame(width) : game.machine->video();
        if (use_565) {
            for (unsigned i = 0; i < pixels.size(); ++i) {
                const Pixel pixel = pixels[i];
                packed_video[i] = ((pixel >> 8) & 0xf800) | ((pixel >> 5) & 0x07e0) | ((pixel >> 3) & 0x001f);
            }
            video_callback(packed_video.data(), width, screen_height, width * sizeof(Word));
        } else {
            video_callback(pixels.data(), width, screen_height, width * sizeof(Pixel));
        }
    }
    auto audio = halted ? std::span<const std::int16_t>(silence) : game.machine->audio();
    if (game.interpolation) {
        const std::size_t split = audio.size() / 4 * 2;
        audio = second ? audio.subspan(split) : audio.first(split);
    }
    if (audio_batch)
        audio_batch(audio.data(), audio.size() / 2);
    else if (audio_sample)
        for (std::size_t i = 0; i < audio.size(); i += 2)
            audio_sample(audio[i], audio[i + 1]);
}

std::FILE *open_cartridge(const char *path)
{
#ifdef _WIN32
    const int length = MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, path, -1, nullptr, 0);
    if (!length)
        return nullptr;
    std::wstring filename(length, L'\0');
    if (!MultiByteToWideChar(CP_UTF8, MB_ERR_INVALID_CHARS, path, -1, filename.data(), length))
        return nullptr;
    return _wfopen(filename.c_str(), L"rb");
#else
    return std::fopen(path, "rb");
#endif
}

} // namespace

#ifdef _WIN32
#define ABI extern "C" __declspec(dllexport)
#else
#define ABI extern "C" __attribute__((visibility("default")))
#endif

ABI unsigned retro_api_version() { return 1; }
ABI void retro_init() {}
ABI void retro_set_environment(Environment callback)
{
    environment = callback;
    if (environment)
        environment(set_variables, options);
}
ABI void retro_set_video_refresh(VideoCallback callback) { video_callback = callback; }
ABI void retro_set_audio_sample(AudioSample callback) { audio_sample = callback; }
ABI void retro_set_audio_sample_batch(AudioBatch callback) { audio_batch = callback; }
ABI void retro_set_input_poll(InputPoll callback) { input_poll = callback; }
ABI void retro_set_input_state(InputState callback) { input_state = callback; }
ABI void retro_set_controller_port_device(unsigned port, unsigned device)
{
    if (port == 0)
        controller = device & 255;
}

ABI void retro_get_system_info(retro_system_info *info)
{
    *info = {"Mark V", "0.5.1", "smp", true, true};
}

ABI void retro_get_system_av_info(retro_system_av_info *info)
{
    *info = av_info(game_session && game_session->machine->bus.widescreen(),
                    game_session && bool(game_session->interpolation));
}

ABI void retro_unload_game()
{
    delete game_session;
    game_session = nullptr;
    halted = false;
}

ABI void retro_deinit() { retro_unload_game(); }

ABI bool retro_load_game(const retro_game_info *game)
{
    retro_unload_game();
    if (!game || !game->path || !environment)
        return false;
    int format = xrgb8888;
    use_565 = !environment(set_pixel_format, &format);
    if (use_565) {
        format = rgb565;
        if (!environment(set_pixel_format, &format))
            return false;
    }
    try {
        const std::unique_ptr<std::FILE, decltype(&std::fclose)> input(open_cartridge(game->path), std::fclose);
        if (!input || std::fseek(input.get(), 0, SEEK_END))
            return false;
        const long length = std::ftell(input.get());
        if (length < 8 || length > 0x400000 || std::fseek(input.get(), 0, SEEK_SET))
            return false;
        auto session = std::make_unique<Game>();
        auto &cartridge = session->cartridge;
        cartridge.resize(static_cast<std::size_t>(length));
        if (std::fread(cartridge.data(), 1, cartridge.size(), input.get()) != cartridge.size())
            return false;
        session->machine = std::make_unique<Machine>(cartridge);
        apply_options(*session, true);
        game_session = session.release();
        environment(set_input_descriptors, inputs);
        return true;
    } catch (const std::exception &error) {
        notify(error.what());
        retro_unload_game();
        return false;
    }
}

ABI void retro_reset()
{
    if (!game_session)
        return;
    try {
        auto replacement = std::make_unique<Machine>(game_session->cartridge);
        const auto &bus = game_session->machine->bus;
        replacement->bus.set_video_options(bus.widescreen(), bus.mark_vi());
        replacement->bus.set_audio_levels(game_session->requested.levels);
        game_session->machine = std::move(replacement);
        game_session->second_half = false;
        if (game_session->interpolation)
            game_session->interpolation->reset();
        halted = false;
    } catch (const std::exception &error) {
        notify(error.what());
    }
}

ABI void retro_run()
{
    if (!game_session)
        return;
    auto &game = *game_session;
    // Finish the previous video/audio pair before consulting new preferences.
    if (game.second_half) {
        game.second_half = false;
        present(game, true);
        return;
    }
    if (input_poll)
        input_poll();
    if (!halted) {
        bool changed = false;
        if (!environment(get_variable_update, &changed) || changed)
            apply_options(game, false);
        run_machine();
    }
    game.second_half = bool(game.interpolation);
    present(game, false);
}

ABI unsigned retro_get_region() { return 0; }
ABI bool retro_load_game_special(unsigned, const retro_game_info *, std::size_t) { return false; }
ABI std::size_t retro_serialize_size() { return 0; }
ABI bool retro_serialize(void *, std::size_t) { return false; }
ABI bool retro_unserialize(const void *, std::size_t) { return false; }
ABI void retro_cheat_reset() {}
ABI void retro_cheat_set(unsigned, bool, const char *) {}
ABI void *retro_get_memory_data(unsigned) { return nullptr; }
ABI std::size_t retro_get_memory_size(unsigned) { return 0; }

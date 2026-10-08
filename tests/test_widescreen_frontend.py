"""Exercise widescreen presentation from the public patch, without MAME/ROMs.

The real retro_run, geometry helpers, option parser and both window aspect
branches are compiled. Only the frontend callbacks and emulation/render bridge
are stubbed. This checks geometry negotiation and the saved120 Hz presentation
queue; renderer pixel fidelity is covered separately.
"""

import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

from test_mdp_raster_cram import PATCH, full_function, patched_fragments

ROOT = Path(__file__).resolve().parents[1]

PROBE = r'''

#include <algorithm>
#include <cassert>
#include <cstring>
#include <iostream>
#include "sh_video_options.h"
#define CORE_NAME "mame"
#define LOG_PIXEL_BYTES 2
#define RETRO_ENVIRONMENT_GET_VARIABLE 1
#define RETRO_ENVIRONMENT_GET_VARIABLE_UPDATE 2
#define RETRO_ENVIRONMENT_SET_GEOMETRY 3
#define RETRO_ENVIRONMENT_SET_MESSAGE 4
#define RETRO_LOG_INFO 1
#define VIDEO_CHANGED_NONE 0
#define VIDEO_CHANGED_GEOMETRY 1
#define VIDEO_CHANGED_AV_INFO 2
struct retro_variable { const char *key; const char *value; };
struct retro_game_geometry {unsigned base_width,base_height,max_width,max_height;float aspect_ratio;};
struct retro_message {const char *message; unsigned frames;};
unsigned fb_width=320,fb_height=224,max_width=4096,max_height=3072;
float retro_aspect=4.f/3;
int video_changed=0,retro_pause=0,RLOOP=0;
bool retro_load_ok=true,autoloadfastforward=false,first_run=false,draw_this_frame=true;
bool led_state_cb=false,has_update=false,has_preference=true,alternate=false;
const char *preference="original";
int geometry_count=0,frame_count=0,native_count=0,checks=0;
float presented_aspect=4.f/3;
unsigned seen_width=0,seen_height=0,seen_max_width=0,seen_max_height=0;
std::uint32_t videoBuffer[426*224]{};
bool environ_cb(unsigned cmd,void *data) {
 if(cmd==RETRO_ENVIRONMENT_GET_VARIABLE){auto &v=*static_cast<retro_variable*>(data); assert(!strcmp(v.key,"mame_mdp_aspect")); v.value=preference;return has_preference;}
 if(cmd==RETRO_ENVIRONMENT_GET_VARIABLE_UPDATE){*static_cast<bool*>(data)=has_update;has_update=false;return true;}
 if(cmd==RETRO_ENVIRONMENT_SET_GEOMETRY){auto &v=*static_cast<retro_game_geometry*>(data);presented_aspect=v.aspect_ratio;seen_max_width=v.max_width;seen_max_height=v.max_height;geometry_count++;return true;}
 return true;
}
namespace sh_mdp_explosions { enum class result {none}; std::atomic<result> notification{result::none}; const char *message(result){return nullptr;} }
void check_variables(){ PARSE }
bool restart_for_explosion_option_change(){return false;}
void update_runtime_variables(bool){}
void update_markvi_refresh(){}
void retro_main_loop(){ native_count++;sh_mdp_video::source_width=sh_mdp_video::widescreen ? 426:320;fb_width=alternate?640:sh_mdp_video::source_width.load();fb_height=alternate?480:224;}
void log_cb(int,const char*,const char*){}
void retro_autoloadfastforwarding(){}
void retro_led_interface(){}
void video_cb(const void*,unsigned width,unsigned height,unsigned){frame_count++;seen_width=width;seen_height=height;}
void audio_batch_cb(const std::int16_t*,unsigned){}
void upload_output_audio_buffer(){}
void update_geometry();
void update_av_info(){}
struct FakeScreen {
 unsigned pixels = 320;
 const FakeScreen &visible_area() const { return *this; }
 unsigned width() const { return pixels; }
};
FakeScreen fake_screen;
bool screen_present = true;
struct FakeMachine { int root_device() const { return 0; } };
FakeMachine machine() { return {}; }
int index() { return 0; }
using screen_device = FakeScreen;
struct screen_device_enumerator {
 explicit screen_device_enumerator(int) {}
 const FakeScreen *byindex(int) const { return screen_present ? &fake_screen : nullptr; }
};
void window_initial_aspect() {
 const screen_device *screen = screen_present ? &fake_screen : nullptr;
 WINDOW_INITIAL
}
float window_updated_aspect(float eff_aspect) {
 WINDOW_UPDATE
 return eff_aspect;
}
PREFIX
UPDATE_GEOMETRY
RUN
void check(bool v){assert(v);checks++;}
void change(const char *value){preference=value;has_update=true;}
int main(){
 using namespace sh_mdp_video;
 check(!request_wide && !widescreen && !wide_eligible);
 request_wide=true; check(aspect_for_source(426,1.5f)==1.5f);
 wide_eligible=true;
 check(aspect_for_source(320,1.5f)==4.f/3);
 check(aspect_for_source(426,1.5f)==16.f/9);
 check(aspect_for_source(640,1.5f)==1.5f);
 has_preference=false;check_variables();check(!request_wide);has_preference=true;
 preference=nullptr;check_variables();check(!request_wide);
 preference="unknown";check_variables();check(!request_wide);
 change("original");retro_run();check(seen_width==320 && presented_aspect==4.f/3 && !widescreen);
 int before=geometry_count;retro_run();check(geometry_count==before);
 change("widescreen");retro_run();check(seen_width==426 && presented_aspect==16.f/9 && widescreen);
 alternate=true;retro_run();check(seen_width==640 && seen_height==480 && presented_aspect==16.f/9);
 change("original");retro_run();check(seen_width==640 && presented_aspect==4.f/3 && !widescreen);
 // A restored half has source width426 but output640x480, while the current
 // preference and native source are320. Never infer from fb_width.
 pending_width=640;pending_height=480;pending_source_width=426;
 pending_draw=false;pending_samples=0;second_half=true;
 before=native_count;retro_run();check(native_count==before && !second_half);
 check(seen_width==640 && presented_aspect==16.f/9);
 retro_run();check(native_count==before+1 && presented_aspect==4.f/3);
 // A runtime preference is read immediately but applied only after pending.
 pending_source_width=320;second_half=true;change("widescreen");
 before=native_count;retro_run();check(native_count==before && request_wide && !widescreen);
 check(presented_aspect==4.f/3);retro_run();check(widescreen && presented_aspect==16.f/9);
 // The real 120 Hz path records the source width for the pending image.
 alternate=false;hz120=true;retro_run();check(second_half && pending_width==426 && pending_source_width==426);
 change("original");before=native_count;retro_run();check(native_count==before && presented_aspect==16.f/9 && widescreen);
 retro_run();check(!widescreen && seen_width==320 && pending_source_width==320 && presented_aspect==4.f/3);
 hz120=false;clear_pending();check(!second_half && pending_source_width==0 && source_width==0);
 wide_eligible=false;change("widescreen");retro_run();check(!widescreen);

 // Both window aspect paths use the real source rectangle, independently of
 // request/host output dimensions. Ordinary games keep their existing aspect.
 clear_pending(); retro_aspect = 1.5f; fake_screen.pixels = 426;
 window_initial_aspect(); check(retro_aspect == 1.5f && source_width == 0);
 check(window_updated_aspect(1.5f) == 1.5f && source_width == 0);
 wide_eligible = true; fake_screen.pixels = 320; request_wide = true;
 window_initial_aspect(); check(retro_aspect == 4.f/3 && source_width == 320);
 check(window_updated_aspect(1.5f) == 4.f/3 && source_width == 320);
 fake_screen.pixels = 426; request_wide = false;
 window_initial_aspect(); check(retro_aspect == 16.f/9 && source_width == 426);
 check(window_updated_aspect(1.5f) == 16.f/9 && source_width == 426);
 fake_screen.pixels = 256; retro_aspect = 1.5f;
 window_initial_aspect(); check(retro_aspect == 1.5f && source_width == 256);
 check(window_updated_aspect(1.5f) == 1.5f && source_width == 256);
 screen_present = false; clear_pending(); retro_aspect = 1.5f;
 window_initial_aspect(); check(retro_aspect == 1.5f && source_width == 0);
 check(window_updated_aspect(1.5f) == 1.5f && source_width == 0);
 // The legacy geometry update path must initialize the entire libretro
 // geometry structure, including maxima, even outside authenticated SH games.
 wide_eligible = false; fb_width = 777; fb_height = 333;
 max_width = 1200; max_height = 900; retro_aspect = 1.5f;
 video_changed = VIDEO_CHANGED_GEOMETRY;
 update_geometry();
 check(seen_max_width == 1200 && seen_max_height == 900);
 check(presented_aspect == 1.5f && video_changed == VIDEO_CHANGED_NONE);
 std::cout<<checks<<" frontend checks passed\n";
}
'''


def probe_source(patch):
    cpp = patched_fragments(patch, "src/osd/libretro/libretro-internal/libretro.cpp")
    window = patched_fragments(patch, "src/osd/libretro/window.cpp")
    prefix = cpp[cpp.index("// Track the geometry actually presented"):
                 cpp.index("void update_geometry(void)")]
    parser = cpp[cpp.index("   struct retro_variable aspect ="):
                 cpp.index("   struct retro_variable sh1_video =")]
    initial_start = window.index("\tif (sh_mdp_video::wide_eligible.load")
    initial = window[initial_start:window.index("\t// reset screen configuration", initial_start)]
    update_start = window.index("\t\tunsigned source_width = 0;")
    update = window[update_start:window.index("\t\ttarget()->compute_minimum_size", update_start)]
    return (PROBE.replace("PARSE", parser).replace("PREFIX", prefix)
            .replace("RUN", full_function(cpp, "void retro_run(void)"))
            .replace("UPDATE_GEOMETRY", full_function(cpp, "void update_geometry(void)"))
            .replace("WINDOW_INITIAL", initial).replace("WINDOW_UPDATE", update))


class WidescreenFrontendTests(unittest.TestCase):
    def test_actual_source_geometry_and_pending_half(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = directory / "widescreen_frontend.cpp"
            source.write_text(probe_source(PATCH.read_text()), encoding="utf-8")
            binary = directory / ("probe.exe" if os.name == "nt" else "probe")
            subprocess.run(shlex.split(os.environ.get("CXX", "c++")) + [
                "-std=c++17", "-Wall", "-Wextra", "-Werror", "-pedantic",
                "-I", str(ROOT / "src/markv"), str(source), "-o", str(binary)
            ], check=True)
            result = subprocess.run([str(binary)], text=True, capture_output=True, check=True)
            self.assertEqual(result.stdout.strip(), "36 frontend checks passed")


if __name__ == "__main__":
    unittest.main()

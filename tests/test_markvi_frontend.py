"""Compile production option selection and presentation cadence without ROMs.

SH1 and SH2 keep independent settings, and only the authenticated cartridge
profile enables Mark VI. The real retro_run loop checks native frame boundaries,
frontend rejection and the pending half-frame queue for both games.
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
#define RETRO_ENVIRONMENT_SET_SYSTEM_AV_INFO 3
#define RETRO_ENVIRONMENT_SET_MESSAGE 4
#define RETRO_LOG_INFO 1
#define VIDEO_CHANGED_NONE 0
#define VIDEO_CHANGED_GEOMETRY 1
#define VIDEO_CHANGED_AV_INFO 2
struct retro_variable {const char *key; const char *value;};
struct retro_game_geometry {unsigned base_width,base_height,max_width,max_height;float aspect_ratio;};
struct retro_system_av_info {
 retro_game_geometry geometry;
 struct {double fps,sample_rate;} timing;
};
struct retro_message {const char *message; unsigned frames;};
unsigned fb_width=320,fb_height=224,max_width=4096,max_height=3072;
float retro_aspect=4.f/3,retro_fps=59.92274475f,sample_rate=48000;
int video_changed=0,retro_pause=0,RLOOP=0;
bool retro_load_ok=true,autoloadfastforward=false,first_run=false,draw_this_frame=false;
bool led_state_cb=false,has_update=false,reject_refresh=false;
bool has_sh1=true,has_sh2=true;
const char *sh1_preference="original",*sh2_preference="original";
int av_count=0,message_count=0,native_count=0,video_count=0,checks=0;
unsigned audio_samples=0;
double announced_fps=0;
std::uint32_t videoBuffer[320*224]{};
bool environ_cb(unsigned cmd,void *data) {
 if(cmd==RETRO_ENVIRONMENT_GET_VARIABLE){
  auto &v=*static_cast<retro_variable*>(data);
  if(!strcmp(v.key,"mame_sh1_rendering")){v.value=sh1_preference;return has_sh1;}
  assert(!strcmp(v.key,"mame_sh2_rendering"));v.value=sh2_preference;return has_sh2;
 }
 if(cmd==RETRO_ENVIRONMENT_GET_VARIABLE_UPDATE){*static_cast<bool*>(data)=has_update;has_update=false;return true;}
 if(cmd==RETRO_ENVIRONMENT_SET_SYSTEM_AV_INFO){av_count++;announced_fps=static_cast<retro_system_av_info*>(data)->timing.fps;return !reject_refresh;}
 if(cmd==RETRO_ENVIRONMENT_SET_MESSAGE){message_count++;return true;}
 return true;
}
namespace sh_mdp_explosions {
 enum class result {none}; std::atomic<result> notification{result::none};
 const char *message(result){return nullptr;}
}
void check_variables(){ PARSE }
bool restart_for_explosion_option_change(){return false;}
void update_runtime_variables(bool){}
void retro_main_loop(){native_count++;}
void log_cb(int,const char*,const char*){}
void retro_autoloadfastforwarding(){}
void retro_led_interface(){}
void video_cb(const void*,unsigned,unsigned,unsigned){video_count++;}
void audio_batch_cb(const std::int16_t*,unsigned count){audio_samples+=count;}
void upload_output_audio_buffer(){}
void prepare_mdp_geometry(unsigned,unsigned,unsigned){}
void update_geometry(){}
void update_av_info(){}
AV_INFO_FUNCTION
static bool rate_request_seen=false,rate_request_value=false;
REFRESH
RUN
// These are the production initial-cadence statements following mmain2.
void initial_cadence(){ INITIAL }
void check(bool v){assert(v);checks++;}
void options(const char *one,const char *two){sh1_preference=one;sh2_preference=two;check_variables();}
void change(const char *one,const char *two){sh1_preference=one;sh2_preference=two;has_update=true;}
void initial(unsigned profile) {
 using namespace sh_mdp_video;
 clear_pending();hz120=false;rate_request_seen=false;
 // Startup reads preferences before the driver authenticates the cartridge.
 set_game(0);check_variables();set_game(profile);initial_cadence();
}
int main(){
 using namespace sh_mdp_video;
 check(game==0 && !markvi && !request_120 && !hz120);
 options("mark_vi_120","mark_vi_120");check(!markvi && !request_120);
 set_game(99);check(game==0 && !markvi && !request_120);
 for(unsigned profile:{1u,2u}) {
  // Each game's setting works with the other game's preference disabled.
  options(profile==1?"mark_vi_120":"original",profile==2?"mark_vi_120":"original");
  initial(profile);check(markvi && request_120 && hz120);
  retro_system_av_info info{};retro_get_system_av_info(&info);
  check(info.timing.fps==double(retro_fps)*2 && info.timing.sample_rate==48000);
  const int before_av=av_count;update_markvi_refresh();check(av_count==before_av);
  set_game(profile==1?2:1);check(!markvi && !request_120);
  // Profile selection never overrides an accepted cadence or pending image.
  second_half=true;check(hz120 && second_half);clear_pending();set_game(profile);
  options(profile==1?"mark_vi":"original",profile==2?"mark_vi":"original");
  initial(profile);check(markvi && !request_120 && !hz120);
  retro_get_system_av_info(&info);check(info.timing.fps==retro_fps);
  // Switch to120, execute exactly one native frame, then finish its queued half
  // before changing cadence. Input/CPU are not advanced for the second half.
  change(profile==1?"mark_vi_120":"original",profile==2?"mark_vi_120":"original");
  int native_before=native_count;retro_run();
  check(hz120 && second_half && native_count==native_before+1);
  pending_samples=20;const auto audio_before=audio_samples;
  change("original","original");retro_run();
  check(hz120 && !second_half && native_count==native_before+1);
  check(audio_samples==audio_before+10 && !markvi && !request_120);
  retro_run();check(!hz120 && native_count==native_before+2);
  // A rejected change is attempted once, keeps the old rate, and informs the
  // frontend. Changing away and back permits an intentional retry.
  reject_refresh=true;
  change(profile==1?"mark_vi_120":"original",profile==2?"mark_vi_120":"original");
  int before_messages=message_count;retro_run();
  check(!hz120 && message_count==before_messages+1);
  const int attempts=av_count;retro_run();check(av_count==attempts);
  change("original","original");retro_run();reject_refresh=false;
  change(profile==1?"mark_vi_120":"original",profile==2?"mark_vi_120":"original");
  retro_run();check(hz120 && second_half);
  clear_pending();hz120=false;
 }
 // Missing, null and unknown settings all recover the faithful default.
 set_game(1);has_sh1=false;options("mark_vi_120","mark_vi_120");check(!markvi && !request_120);
 has_sh1=true;options(nullptr,"mark_vi_120");check(!markvi && !request_120);
 options("invalid","mark_vi_120");check(!markvi && !request_120);
 set_game(2);has_sh2=false;options("mark_vi_120","mark_vi_120");check(!markvi && !request_120);
 has_sh2=true;options("mark_vi_120",nullptr);check(!markvi && !request_120);
 options("mark_vi_120","invalid");check(!markvi && !request_120);
 // Unrelated cartridges retain native cadence despite either stored setting.
 options("mark_vi_120","mark_vi_120");initial(0);check(!markvi && !request_120 && !hz120);
 retro_system_av_info info{};retro_get_system_av_info(&info);check(info.timing.fps==retro_fps);
 retro_run();check(!hz120 && !second_half);
 // No loaded content can activate a new cadence.
 set_game(1);retro_load_ok=false;rate_request_seen=false;update_markvi_refresh();check(!hz120);
 std::cout<<checks<<" Mark VI frontend checks passed\n";
}
'''


def probe_source(cpp):
    parser = cpp[cpp.index('   struct retro_variable sh1_video ='):
                 cpp.index('   // Atomic preferences are consumed')]
    initial_start = cpp.index('   sh_mdp_video::apply_rendering_options();',
                              cpp.index('   update_runtime_variables(true);'))
    initial = cpp[initial_start:cpp.index('   sh_mdp_video::widescreen.store(', initial_start)]
    return (PROBE.replace('PARSE', parser).replace('INITIAL', initial)
            .replace('AV_INFO_FUNCTION', full_function(cpp, 'void retro_get_system_av_info(struct retro_system_av_info *info)'))
            .replace('REFRESH', full_function(cpp, 'static void update_markvi_refresh()'))
            .replace('RUN', full_function(cpp, 'void retro_run(void)')))


class MarkVIFrontendTests(unittest.TestCase):
    def test_independent_profiles_and_refresh_boundaries(self):
        cpp = patched_fragments(PATCH.read_text(), 'src/osd/libretro/libretro-internal/libretro.cpp')
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            source = directory/'markvi_frontend.cpp'
            source.write_text(probe_source(cpp), encoding='utf-8')
            binary = directory/('probe.exe' if os.name == 'nt' else 'probe')
            subprocess.run(shlex.split(os.environ.get('CXX', 'c++')) + [
                '-std=c++17', '-Wall', '-Wextra', '-Werror', '-pedantic',
                '-I', str(ROOT/'src/markv'), str(source), '-o', str(binary)
            ], check=True)
            result = subprocess.run([str(binary)], text=True, capture_output=True, check=True)
            self.assertEqual(result.stdout.strip(), '41 Mark VI frontend checks passed')


if __name__ == '__main__':
    unittest.main()

#!/usr/bin/env python3
"""Compare optional SH2 rendering with private ROMs; publish hashes only.

Game RAM and CPU registers are sampled into a temporary file, hashed and removed.
Optional screenshots require an explicit local output directory and are private.
"""
import argparse
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

from libretro_regression import GameInfo, Variable
from libretro_explosion_regression import ExplosionFrontend, snapshot
from libretro_state_regression import first_video_difference, first_audio_difference
from libretro_deflicker_regression import IDENTITIES


class Geometry(C.Structure):
    _fields_ = [('width', C.c_uint), ('height', C.c_uint), ('max_width', C.c_uint), ('max_height', C.c_uint), ('aspect', C.c_float)]

class Timing(C.Structure):
    _fields_ = [('fps', C.c_double), ('sample_rate', C.c_double)]

class AVInfo(C.Structure):
    _fields_ = [('geometry', Geometry), ('timing', Timing)]

class RenderingFrontend(ExplosionFrontend):
    def __init__(self, *args, rendering, deflicker, capture_dir, **kwargs):
        self.loading = False
        self.resolution = None
        self.double_rate = False
        self.reject_120 = False
        self.aspect = b"original"
        self.rendering = rendering.encode()
        self.deflicker = deflicker.encode()
        self.capture_dir = capture_dir
        super().__init__(*args, **kwargs)

    def environment(self, command, data):
        if command == 37:
            info = C.cast(data, C.POINTER(Geometry)).contents
            self.report.setdefault('geometry_updates', []).append({'frame':self.frame,'width':info.width,'height':info.height,'aspect':info.aspect})
            return True
        if command == 32:
            if self.loading:
                self.report['av_update_during_load'] = True
            info = C.cast(data, C.POINTER(AVInfo)).contents
            accepted = not (self.reject_120 and info.timing.fps > 100)
            self.report.setdefault('av_updates', []).append({'frame': self.frame, 'fps': info.timing.fps, 'sample_rate': info.timing.sample_rate, 'accepted': accepted})
            if not accepted:
                return False
            self.double_rate = info.timing.fps > 100
        if command == 15:
            v = C.cast(data, C.POINTER(Variable)).contents
            if self.resolution and v.key in (b'mame_alternate_renderer', b'mame_altres'):
                v.value = b'enabled' if v.key == b'mame_alternate_renderer' else self.resolution
                return True
            if v.key == b'mame_mdp_aspect':
                v.value = self.aspect
                return True
            if v.key == b'mame_sh2_rendering':
                self.report['rendering_queried'] = True
                if self.rendering == b'missing':
                    return False
                v.value = self.rendering
                return True
            if v.key == b'mame_sh2_deflicker':
                v.value = self.deflicker
                return True
        return super().environment(command, data)

    def input_state(self, port, device, index, control):
        saved = self.frame
        if self.double_rate:
            self.frame = (self.frame + 1) // 2
        try:
            return super().input_state(port, device, index, control)
        finally:
            self.frame = saved

    def video(self, data, width, height, pitch):
        super().video(data, width, height, pitch)
        sizes = self.report.setdefault('video_sizes', [])
        if not sizes or sizes[-1]['width'] != width or sizes[-1]['height'] != height:
            sizes.append({'frame':self.frame,'width':width,'height':height})
        if self.capture_dir and self.last_frame and self.capture_start <= self.frame <= self.capture_end and self.frame % self.capture_step == 0:
            from PIL import Image
            packed, w, h = self.last_frame
            Image.frombytes('RGB', (w, h), packed, 'raw', 'BGRX').save(
                self.capture_dir / f'frame-{self.frame:05d}.png')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--core', type=Path, required=True)
    p.add_argument('--rom', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    p.add_argument('--rendering', default='original', choices=['original','mark_vi','mark_vi_120','missing','invalid'])
    p.add_argument('--aspect', default='original', choices=['original','widescreen'])
    p.add_argument('--aspect-toggle', action='store_true')
    p.add_argument('--deflicker', default='game', choices=['game','off','on1','on2'])
    p.add_argument('--input', default='reference', choices=['reference','stage3fire','stage4fire','stage5fire','scripted','attract'])
    p.add_argument('--frames', type=int, default=7000)
    p.add_argument('--state-frames', type=int, default=120)
    p.add_argument('--baseline', type=Path)
    p.add_argument('--expect-video', default='same', choices=['same','different'])
    p.add_argument('--threaded', action='store_true')
    p.add_argument('--toggle', action='store_true')
    p.add_argument('--donor', type=Path)
    p.add_argument('--capture-dir', type=Path)
    p.add_argument('--capture-start', type=int, default=0)
    p.add_argument('--capture-end', type=int, default=2**31-1)
    p.add_argument('--capture-step', type=int, default=10)
    p.add_argument('--resolution', help='Exercise the MAME software renderer at an alternate resolution, e.g. 640x480')
    p.add_argument('--reject-120', action='store_true', help='Simulate a frontend refusing the 120 Hz request')
    p.add_argument('--half-state', action='store_true', help='Also replay a state taken between two 120 Hz halves')
    a = p.parse_args()
    if a.frames < 240 or a.state_frames < 1:
        p.error('at least 240 frames and a positive replay window are required')
    game = IDENTITIES[hashlib.sha1(a.rom.read_bytes()).hexdigest()][0]
    report = dict(passed=False, game=game, rendering=a.rendering, deflicker=a.deflicker, aspect=a.aspect,
                  input=a.input, frames=a.frames, threaded=a.threaded,
                  core_sha256=hashlib.sha256(a.core.read_bytes()).hexdigest(), messages=[])
    if a.capture_dir:
        a.capture_dir.mkdir(parents=True, exist_ok=True)
    try:
        with tempfile.TemporaryDirectory(prefix='sh-rendering-') as temporary:
            temp = Path(temporary)
            for name in ('cart','system','save'):
                (temp/name).mkdir()
            rom = temp/'cart'/a.rom.name
            shutil.copyfile(a.rom, rom)
            if a.donor:
                shutil.copyfile(a.donor, temp/'system'/'jp_jp_space_harrier.smp')
            audit = temp/'audit.bin'
            script = temp/'audit.lua'
            script.write_text(f'''
local cpu=manager.machine.devices[":maincpu"]
local mem=cpu.spaces["program"]
local frame=0
local out=assert(io.open("{audit}","ab"))
FRAME=emu.add_machine_frame_notifier(function()
 frame=frame+1
 if frame%120==0 then
  out:write(mem:read_range(0xfe0000,0xffffff,8))
  for _,name in ipairs({{"PC","SR","D0","D1","D2","D3","D4","D5","D6","D7","A0","A1","A2","A3","A4","A5","A6","SP"}}) do
   out:write(string.pack(">I4",cpu.state[name].value & 0xffffffff))
  end
  out:flush()
 end
end)
STOP=emu.add_machine_stop_notifier(function() out:close() end)
''')
            content = temp/'game.cmd'
            content.write_text(f'megadrij -skip_gameinfo -autoboot_delay 0 -autoboot_script {script} -cart {rom}\n')
            f = RenderingFrontend(a.core.resolve(), content, 'sh1' if a.donor else 'original', a.input, report,
                                  rendering=a.rendering, deflicker=a.deflicker, capture_dir=a.capture_dir)
            f.aspect = a.aspect.encode()
            f.resolution = a.resolution.encode() if a.resolution else None
            report['resolution'] = a.resolution
            f.reject_120 = a.reject_120
            f.capture_start, f.capture_end, f.capture_step = a.capture_start, a.capture_end, a.capture_step
            f.thread_mode_value = b'enabled' if a.threaded else b'disabled'
            f.system_dir = os.fsencode(temp/'system'); f.save_dir = os.fsencode(temp/'save')
            core=f.core
            for setter, callback in zip(('retro_set_environment','retro_set_video_refresh','retro_set_audio_sample','retro_set_audio_sample_batch','retro_set_input_poll','retro_set_input_state'), f._callbacks):
                getattr(core,setter)(callback)
            core.retro_load_game.argtypes=[C.POINTER(GameInfo)];core.retro_load_game.restype=C.c_bool
            core.retro_serialize_size.restype=C.c_size_t
            for name in ('retro_serialize','retro_unserialize'):
                getattr(core,name).argtypes=[C.c_void_p,C.c_size_t];getattr(core,name).restype=C.c_bool
            core.retro_init();loaded=False
            def replay():
                state,size=snapshot(core);saved=(f.frame,f.last_frame,f.frames_seen)
                first=f.run_window(f.frame+1,a.state_frames)
                assert core.retro_unserialize(state,size)
                f.frame,f.last_frame,f.frames_seen=saved
                second=f.run_window(f.frame+1,a.state_frames)
                assert first_video_difference(first,second) is None
                assert first_audio_difference(first,second) is None
                state.check_guards()
                return {'passed':True,'capacity':size,'frames':a.state_frames}
            try:
                gi=GameInfo(os.fsencode(content),None,0,None)
                if a.reject_120:
                    f.rendering=b'mark_vi'  # Refusal applies to runtime changes, not the initial AV query.
                f.loading=True
                loaded=bool(core.retro_load_game(C.byref(gi)));f.loading=False;assert loaded
                assert not report.get('av_update_during_load', False)
                core.retro_get_system_av_info.argtypes=[C.POINTER(AVInfo)]
                info=AVInfo();core.retro_get_system_av_info(C.byref(info))
                f.double_rate=info.timing.fps>100
                report.setdefault('av_updates', []).append({'frame':0,'fps':info.timing.fps,'sample_rate':info.timing.sample_rate,'initial_query':True,'accepted':True})
                if a.reject_120:
                    f.rendering=a.rendering.encode();f.option_update_pending=True
                stream=f.run_window(1,a.frames)
                report['stream']=stream.summary()
                if not a.resolution:
                    assert f.last_frame[1] == (426 if a.aspect == 'widescreen' else 320), f.last_frame[1:]
                if a.rendering == 'mark_vi_120' and game == 2 and not a.reject_120:
                    hashes = {x['frame']: x['sha256'] for x in report['stream']['video_frame_hashes']}
                    pairs = [(i, i+1) for i in hashes if i%2 and i+1 in hashes]
                    report['distinct_half_pairs'] = sum(hashes[x]!=hashes[y] for x,y in pairs)
                    assert any(119 < x['fps'] < 121 for x in report.get('av_updates', []))
                    assert report['distinct_half_pairs'] > 0
                report['state']=replay()
                audit_data = None
                if a.half_state:
                    assert a.rendering == 'mark_vi_120' and game == 2 and a.frames % 2 == 0
                    audit_data = audit.read_bytes()  # Keep the main comparison window identical.
                    f.run_window(f.frame+1, 1)
                    report['half_state']=replay()
                    f.run_window(f.frame+1, 1)  # Complete the pair before cadence-switch comparisons.
                if a.aspect_toggle:
                    report['aspect_toggles']=[]
                    for aspect in ('original','widescreen','original','widescreen'):
                        f.aspect=aspect.encode();f.option_update_pending=True
                        f.run_window(f.frame+1,240)
                        size=f.last_frame[1:]
                        if not a.resolution:assert size[0]==(426 if aspect=='widescreen' else 320),size
                        report['aspect_toggles'].append({'aspect':aspect,'size':size,'state':replay()})
                if a.toggle:
                    report['toggles']=[]
                    # Restore one game state before each mode. Repeating a mode
                    # must reproduce video/PCM, and mode changes must not restart.
                    state,size=snapshot(core);saved=(f.frame,f.last_frame,f.frames_seen)
                    results={}
                    for mode in ('original',a.rendering,'original',a.rendering):
                        assert core.retro_unserialize(state,size)
                        f.frame,f.last_frame,f.frames_seen=saved
                        f.rendering=mode.encode();f.option_update_pending=True
                        if a.rendering == 'mark_vi_120' and game == 2 and not a.reject_120:
                            f.frame = saved[0] if mode == 'mark_vi_120' else saved[0] // 2
                        capture=f.run_window(f.frame+1,600 if mode=='mark_vi_120' and game==2 else 300)
                        if mode in results:
                            assert first_video_difference(results[mode],capture) is None
                            assert first_audio_difference(results[mode],capture) is None
                        results[mode]=capture
                        summary=capture.summary();summary.pop('video_frame_hashes')
                        report['toggles'].append({'mode':mode,'stream':summary,'state':replay()})
                    assert results['original'].audio==results[a.rendering].audio
                    report['toggle_video_differs']=first_video_difference(results['original'],results[a.rendering]) is not None
            finally:
                if loaded:core.retro_unload_game()
                core.retro_deinit()
            data=audit_data if audit_data is not None else audit.read_bytes()
            block=131072+18*4
            assert data and len(data)%block==0
            report['game_audit']={'sha256':hashlib.sha256(data).hexdigest(),'samples':len(data)//block,'interval_video_frames':120,'bytes_per_sample':block}
            if a.baseline:
                b=json.loads(a.baseline.read_text())
                before=b['stream'];after=report['stream']
                report['comparison']={
                    'audio_equal':all(before[k]==after[k] for k in ('audio_sha256','audio_stereo_frames')),
                    'game_audit_equal':b['game_audit']==report['game_audit'],
                    'video_equal':before['video_sha256']==after['video_sha256'],
                    'changed_frames':sum(x!=y for x,y in zip(before['video_frame_hashes'],after['video_frame_hashes']))}
                if a.rendering == 'mark_vi_120' and b['rendering'] != 'mark_vi_120' and game == 2 and not a.reject_120:
                    assert a.frames == b['frames'] * 2
                else:
                    assert len(before['video_frame_hashes'])==len(after['video_frame_hashes'])
                assert report['comparison']['audio_equal'] and report['comparison']['game_audit_equal']
                assert report['comparison']['video_equal']==(a.expect_video=='same')
            report['passed']=True
    except Exception as error:
        report['error']=f'{type(error).__name__}: {error}'
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k in ('passed','error','comparison','game_audit')}))
    return 0 if report['passed'] else 1


if __name__=='__main__':raise SystemExit(main())

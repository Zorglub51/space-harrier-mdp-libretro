#!/usr/bin/env python3
"""Exercise native Deflicker options with private ROMs and isolated state folders.

An optional Lua diagnostic forces the original RAM byte for comparison with a
reference core. Reports include only hashes, counters and option values.
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
from libretro_explosion_regression import ExplosionFrontend, StateBuffer
from libretro_state_regression import first_video_difference, first_audio_difference

IDENTITIES = {
    'e87e9338d7842db68a7a1e77bd5fc5b2bc8b2b72': (1, 0xff3c36),
    '80f576af01d6413c0b92073e2f947b0431f12a74': (2, 0xff2e62),
}


class DeflickerFrontend(ExplosionFrontend):
    def __init__(self, *args, game, mode, other_mode, **kwargs):
        self.game = game
        self.mode = mode.encode()
        self.other_mode = other_mode.encode()
        super().__init__(*args, **kwargs)

    def environment(self, command, data):
        if command == 15:
            v = C.cast(data, C.POINTER(Variable)).contents
            if v.key in (b'mame_sh1_deflicker', b'mame_sh2_deflicker'):
                self.report.setdefault('queried', []).append(v.key.decode())
                value = self.mode if v.key == f'mame_sh{self.game}_deflicker'.encode() else self.other_mode
                if value == b'missing':
                    return False
                v.value = value
                return True
        return super().environment(command, data)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--core', type=Path, required=True)
    p.add_argument('--rom', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    p.add_argument('--mode', default='game', choices=['game', 'off', 'on1', 'on2', 'missing', 'invalid'])
    p.add_argument('--other-mode', default='game', choices=['game', 'off', 'on1', 'on2'])
    p.add_argument('--frames', type=int, default=4000)
    p.add_argument('--state-frames', type=int, default=120)
    p.add_argument('--toggle', action='store_true')
    p.add_argument('--threaded', action='store_true')
    p.add_argument('--native-reference', type=int, choices=[0, 1, 2])
    p.add_argument('--baseline', type=Path)
    p.add_argument('--donor', type=Path)
    a = p.parse_args()
    game, address = IDENTITIES[hashlib.sha1(a.rom.read_bytes()).hexdigest()]
    report = dict(passed=False, game=game, mode=a.mode, other_mode=a.other_mode,
                  core_sha256=hashlib.sha256(a.core.read_bytes()).hexdigest(),
                  frames=a.frames, native_reference=a.native_reference, threaded=a.threaded,
                  messages=[], scope='Native setting reads, video/PCM, runtime switching and same-option state replay; not a full-game fidelity claim.')
    try:
        with tempfile.TemporaryDirectory(prefix='sh-deflicker-') as temp:
            temp = Path(temp)
            for name in ('cart', 'system', 'save'):
                (temp / name).mkdir()
            rom = temp / 'cart' / a.rom.name
            shutil.copyfile(a.rom, rom)
            if a.donor:
                shutil.copyfile(a.donor, temp / 'system' / 'jp_jp_space_harrier.smp')
            samples = temp / 'readings.txt'
            script = temp / 'trace.lua'
            script.write_text(f'''
local cpu=manager.machine.devices[":maincpu"]
local mem=cpu.spaces["program"]
local out=assert(io.open("{samples}","a"))
out:write("start\\n");out:flush()
local frame=0
local counts={{}}
local addr={address}
TAP=mem:install_read_tap(addr,addr+1,"native_setting_audit",function(offset,data,mask)
  if mask & 0xff00 ~= 0 then
    local pc=cpu.state["PC"].value & 0xffffff
    counts[pc]=(counts[pc] or 0)+1
  end
  return data
end)
FRAME=emu.add_machine_frame_notifier(function()
  frame=frame+1
  if {a.native_reference if a.native_reference is not None else -1} >= 0 and frame >= 120 then
    mem:write_u8(addr,{a.native_reference or 0})
  end
  if frame % 100 == 0 then
    out:write(string.format("value %d %d\\n",frame,mem:read_u8(addr)));out:flush()
  end
end)
STOP=emu.add_machine_stop_notifier(function()
  for pc,n in pairs(counts) do out:write(string.format("read %06X %d\\n",pc,n)) end
  out:close()
end)
''')
            content = temp / 'game.cmd'
            content.write_text(f'megadrij -skip_gameinfo -autoboot_delay 0 -autoboot_script {script} -cart {rom}\n')
            f = DeflickerFrontend(a.core.resolve(), content, 'sh1' if a.donor else 'original',
                                 'scripted' if game == 1 else 'reference', report,
                                 game=game, mode=a.mode, other_mode=a.other_mode)
            f.system_dir = os.fsencode(temp / 'system'); f.save_dir = os.fsencode(temp / 'save')
            f.thread_mode_value = b'enabled' if a.threaded else b'disabled'
            core = f.core
            for setter, cb in zip(('retro_set_environment','retro_set_video_refresh','retro_set_audio_sample','retro_set_audio_sample_batch','retro_set_input_poll','retro_set_input_state'), f._callbacks):
                getattr(core, setter)(cb)
            core.retro_load_game.argtypes=[C.POINTER(GameInfo)]; core.retro_load_game.restype=C.c_bool
            core.retro_serialize_size.restype=C.c_size_t
            for name in ('retro_serialize','retro_unserialize'):
                getattr(core,name).argtypes=[C.c_void_p,C.c_size_t]; getattr(core,name).restype=C.c_bool
            core.retro_init(); loaded=False
            try:
                gi=GameInfo(os.fsencode(content),None,0,None)
                loaded=bool(core.retro_load_game(C.byref(gi))); assert loaded
                stream=f.run_window(1,a.frames).summary();stream.pop('video_frame_hashes')
                report['stream']=stream
                def replay():
                    buffer=StateBuffer(int(core.retro_serialize_size())); assert core.retro_serialize(buffer,buffer.size)
                    saved=(f.frame,f.last_frame,f.frames_seen)
                    first=f.run_window(f.frame+1,a.state_frames)
                    assert core.retro_unserialize(buffer,buffer.size)
                    f.frame,f.last_frame,f.frames_seen=saved
                    second=f.run_window(f.frame+1,a.state_frames)
                    assert first_video_difference(first,second) is None
                    assert first_audio_difference(first,second) is None
                    buffer.check_guards()
                    return dict(passed=True,capacity=buffer.size,frames=a.state_frames)
                report['state']=replay()
                if a.toggle:
                    report['toggles']=[]
                    for mode in ('on1','on2','off','game'):
                        f.mode=mode.encode(); f.option_update_pending=True
                        f.run_window(f.frame+1,300)
                        state_result=replay()
                        values=[int(line.split()[2]) for line in samples.read_text().splitlines() if line.startswith('value ')]
                        effective=values[-1]
                        assert effective=={'game':0,'off':0,'on1':1,'on2':2}[mode], (mode,effective)
                        report['toggles'].append(dict(mode=mode,effective=effective,state=state_result))
                    f.mode=b'on2'; f.option_update_pending=True
                    core.retro_reset(); f.run_window(f.frame+1,1500)
                    report['reset_state']=replay()
            finally:
                if loaded:core.retro_unload_game()
                core.retro_deinit()
            lines=samples.read_text().splitlines()
            report['script_starts']=lines.count('start')
            if a.toggle:assert report['script_starts']==2, 'unexpected game restart during option changes'
            report['readings']=[list(map(int,l.split()[1:])) for l in lines if l.startswith('value ')]
            report['native_reads']={l.split()[1]:int(l.split()[2]) for l in lines if l.startswith('read ')}
            assert report['readings'], 'Lua setting samples missing'
            if not a.toggle:
                expect = a.native_reference if a.native_reference is not None else {'off':0,'on1':1,'on2':2}.get(a.mode,0)
                assert all(v==expect for fr,v in report['readings'] if fr>=200), report['readings']
            else:
                values={v for _,v in report['readings']}
                assert values=={0,1,2}, values
                assert all(v==2 for _,v in report['readings'][-10:]), 'override lost after reset'
            if a.baseline:
                baseline=json.loads(a.baseline.read_text())
                report['baseline_equal']=stream==baseline['stream'];assert report['baseline_equal']
            report['passed']=True
    except Exception as exc:
        report['error']=f'{type(exc).__name__}: {exc}'
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k in ('passed','game','mode','error')}))
    return 0 if report['passed'] else 1


if __name__=='__main__':
    raise SystemExit(main())

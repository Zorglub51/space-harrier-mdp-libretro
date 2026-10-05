"""Execute the complete MDP fill method and its real data-port dispatch prefix.

The original ARM fixture supplies synthetic memory hashes and register states.
The actual register-write branch is also compiled to cover an interrupted fill.
Other control-port execution, ordinary MD fallback and native diagnostic
machinery are outside this probe. Native control steps select pre-fill state.
No MAME checkout or game ROM is needed.
"""
import hashlib
import json
import os
from pathlib import Path
import shlex
import struct
import subprocess
import tempfile
import unittest

from test_mdp_raster_cram import PATCH, full_function, patched_fragments

FIXTURE = Path(__file__).resolve().parent / 'fixtures/mdp_transfer_m2.json'
BINARY_SHA256 = '2374ddca2241d2a040f587a1e86359c3d3d5f1dc93e566588b35e15bee73178f'
BANKS = {'vram': (131072, 13), 'cram': (256, 71), 'vsram': (128, 149)}
HEADER_WORDS = 7 + 64
RESULT_BYTES = HEADER_WORDS * 4 + sum(size for size, _ in BANKS.values())


def probe_source():
    source = patched_fragments(PATCH.read_text(), 'src/devices/video/315_5313.cpp')
    fill = full_function(source, 'void sega315_5313_device::mdp_vram_fill(u16 data)')
    start = source.index('void sega315_5313_device::data_port_w(int data)')
    end = source.index('\n\t/*\n\t0000b : VRAM read', start)
    dispatch = source[start:end] + '\n ++fallback_calls;\n}\n'
    start = source.index('vdp_set_register(regnum & 0x1f, value);')
    end = source.index('\n\t\t}\n\t\telse', start)
    register = ('void sega315_5313_device::register_write(unsigned data) {\n'
                'const int regnum=(data>>8)&63, value=data&255;\n' +
                source[start:end] + '\n}\n')
    return r'''
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <iostream>
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif
using u8=std::uint8_t; using u16=std::uint16_t; using u32=std::uint32_t;
class sega315_5313_device {
public:
 bool m_mdp_scaler=true;
 u16 m_regs[64]{};
 u16 m_vdp_code=0,m_vdp_address=0,m_vram_fill_length=0;
 int m_vram_fill_pending=0,m_command_pending=0;
 unsigned fallback_calls=0,diagnostic_calls=0;
 std::array<u8,131072> vram{};
 std::array<u8,256> cram{};
 std::array<u8,128> vsram{};
 void vram_w(u32 index,u16 data,u16 mask){
  if(index>=32768)std::abort();
  u16 word=u16(vram[index*2])|(u16(vram[index*2+1])<<8);
  word=(word&~mask)|(data&mask);
  vram[index*2]=u8(word);vram[index*2+1]=u8(word>>8);
 }
 template<typename... Args> void logerror(const char*,Args...){++diagnostic_calls;}
 void mdp_vram_fill(u16 data);
 void data_port_w(int data);
 void register_write(unsigned data);
 void vdp_set_register(unsigned index,unsigned value){m_regs[index]=u16(value);}
};
FILL
DISPATCH
REGISTER
void word(u32 value){for(unsigned i=0;i<4;++i)std::cout.put(char(value>>(i*8)));}
template<std::size_t N>void seed(std::array<u8,N>& bank,unsigned salt){
 for(unsigned i=0;i<N;++i)bank[i]=u8(i*37+salt);
}
template<std::size_t N>void output(const std::array<u8,N>& bank){
 std::cout.write(reinterpret_cast<const char*>(bank.data()),N);
}
int main(){
#ifdef _WIN32
 if(_setmode(_fileno(stdout),_O_BINARY)==-1)return 5;
#endif
 unsigned mdp,code,address,fill_pending,command_pending,fill_length,count;
 while(std::cin>>mdp>>code>>address>>fill_pending>>command_pending>>fill_length>>count){
  sega315_5313_device v;
  v.m_mdp_scaler=mdp;v.m_vdp_code=u16(code);v.m_vdp_address=u16(address);
  v.m_vram_fill_pending=fill_pending;v.m_command_pending=command_pending;
  v.m_vram_fill_length=u16(fill_length);
  for(auto& r:v.m_regs){unsigned value;if(!(std::cin>>value))return 2;r=u16(value);}
  seed(v.vram,13);seed(v.cram,71);seed(v.vsram,149);
  for(unsigned i=0;i<count;++i){
   unsigned action,data;if(!(std::cin>>action>>data))return 3;
   if(action==0)v.data_port_w(data);else if(action==1)v.register_write(data);else return 4;
   word(v.m_vdp_code);word(v.m_vdp_address);word(v.m_vram_fill_pending);
   word(v.m_command_pending);word(v.fallback_calls);word(v.diagnostic_calls);
   word(v.m_vram_fill_length);for(auto r:v.m_regs)word(r);
   output(v.vram);output(v.cram);output(v.vsram);
  }
 }
 return std::cin.eof()?0:4;
}
'''.replace('FILL', fill).replace('DISPATCH', dispatch).replace('REGISTER', register)


def run_cases(probe, requests):
    text = []
    for request in requests:
        state = request['state']
        commands = request.get('commands', [(0, data) for data in request.get('data', [])])
        text.append(' '.join(map(str, [request.get('mdp', 1), state['code'], state['address'],
                    request.get('fill_pending', 1), int(state['command_pending']),
                    request.get('fill_length', 0x9876), len(commands)] +
                    state['registers'] + [value for command in commands for value in command])))
    result = subprocess.run([str(probe)], input=('\n'.join(text) + '\n').encode(),
                            capture_output=True, check=True, timeout=30)
    count = sum(len(request.get('commands', request.get('data', []))) for request in requests)
    if len(result.stdout) != count * RESULT_BYTES:
        raise AssertionError('incomplete state or memory output from production fill probe')
    outputs = []
    for offset in range(0, len(result.stdout), RESULT_BYTES):
        header = struct.unpack_from('<' + 'I' * HEADER_WORDS, result.stdout, offset)
        row = dict(zip(('code', 'address', 'fill_pending', 'command_pending',
                        'fallback_calls', 'diagnostic_calls', 'fill_length'), header[:7]))
        row['registers'] = list(header[7:])
        offset += HEADER_WORDS * 4
        row['memory'] = {}
        for bank, (size, _) in BANKS.items():
            row['memory'][bank] = result.stdout[offset:offset + size]
            offset += size
        outputs.append(row)
    return outputs


def fill_steps(fixture):
    """Select the first fill data write using executed native control state."""
    result = []
    for case in fixture['cases']:
        if case['kind'] not in ('fill', 'fill_diagnostic'):
            continue
        before = dict(case['input'], command_pending=bool(case['input']['flags'] & 8))
        for step in case['steps']:
            if (step['write']['address'] & 31) in (0, 2):
                result.append((case, before, step))
                break
            before = step['state']
    return result


class MdpTransferTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temporary.cleanup)
        directory = Path(cls.temporary.name)
        source = directory / 'mdp-fill-probe.cpp'
        source.write_text(probe_source())
        cls.probe = directory / ('mdp-fill-probe.exe' if os.name == 'nt' else 'mdp-fill-probe')
        subprocess.run(shlex.split(os.environ.get('CXX', 'c++')) + [
            '-std=c++17', '-Wall', '-Wextra', '-Werror', str(source), '-o', str(cls.probe),
        ], check=True)

    def compare(self, fixture):
        self.assertEqual(fixture['binary_sha256'], BINARY_SHA256)
        selected = fill_steps(fixture)
        self.assertGreaterEqual(len(selected), 38)
        self.assertEqual(len({case['name'] for case, _, _ in selected}), len(selected))
        requests = []
        for _, before, step in selected:
            for latch in (0, 1):
                requests.append({'state': before, 'data': [step['write']['data']],
                                 'fill_pending': latch})
        rows = run_cases(self.probe, requests)
        for index, (case, before, expected) in enumerate(selected):
            for latch in (0, 1):
                with self.subTest(case=case['name'], pending_fill_latch=latch):
                    actual = rows[index * 2 + latch]
                    for key in ('code', 'address', 'command_pending', 'registers'):
                        self.assertEqual(actual[key], expected['state'][key])
                    self.assertEqual(actual['fallback_calls'], 0)
                    for bank in BANKS:
                        self.assertEqual(hashlib.sha256(actual['memory'][bank]).hexdigest(),
                                         expected['memory'][bank]['sha256'], bank)
                    if expected['boundary'] == 'return':
                        self.assertEqual(actual['fill_pending'], 0)
                        self.assertEqual(actual['diagnostic_calls'], 0)
                    else:
                        # The port logs unsupported fill codes; original execution
                        # stops at its diagnostic call. Memory/state above must agree.
                        self.assertEqual(expected['boundary'], 'diagnostic')
                        self.assertEqual(actual['diagnostic_calls'], 1)

    def test_full_fill_memory_and_state_match_original(self):
        self.compare(json.loads(FIXTURE.read_text()))

    def test_real_dispatch_does_not_reenter_fill_after_completion(self):
        fixture = json.loads(FIXTURE.read_text())
        case, before, first = next(row for row in fill_steps(fixture)
                                  if row[0]['name'] == 'fill_second_data_diagnostic')
        last = case['steps'][-1]
        self.assertEqual(last['boundary'], 'diagnostic')
        rows = run_cases(self.probe, [{'state': before, 'data': [first['write']['data'],
                                                             last['write']['data']]}])
        self.assertEqual(rows[0]['fallback_calls'], 0)
        self.assertEqual(rows[1]['fallback_calls'], 1)
        self.assertEqual(rows[1]['fill_pending'], 0)
        self.assertEqual(rows[1]['memory'], rows[0]['memory'])
        self.assertEqual(rows[1]['registers'], last['state']['registers'])
        self.assertEqual(rows[1]['code'], last['state']['code'])
        self.assertEqual(rows[1]['address'], last['state']['address'])

    def test_dispatch_preserves_ordinary_md_and_rejects_other_mdp_dma_types(self):
        fixture = json.loads(FIXTURE.read_text())
        _, before, step = next(row for row in fill_steps(fixture)
                               if row[0]['name'] == 'fill_length_4')
        requests = [{'state': before, 'data': [step['write']['data']], 'mdp': 0}]
        for dma_type in (0, 0x40, 0xc0):
            state = dict(before, registers=before['registers'].copy())
            state['registers'][23] = dma_type
            requests.append({'state': state, 'data': [step['write']['data']]})
        for index, actual in enumerate(run_cases(self.probe, requests)):
            self.assertEqual(actual['fallback_calls'], int(index == 0))
            self.assertEqual(actual['diagnostic_calls'], int(index != 0))
            for bank, (size, salt) in BANKS.items():
                self.assertEqual(actual['memory'][bank],
                                 bytes((i * 37 + salt) & 255 for i in range(size)))

    def test_copy_mode_data_write_matches_native_sh_profile_diagnostic(self):
        fixture = json.loads(FIXTURE.read_text())
        # Profile 0 is the generic native path used by SH1/SH2. The fixture's
        # unrelated title-specific profile exceptions are outside this core.
        case = next(c for c in fixture['cases'] if c['name'] == 'data_code21_typeC0_profile_0')
        before = dict(case['input'], command_pending=bool(case['input']['flags'] & 8))
        expected = case['steps'][0]
        self.assertEqual(expected['boundary'], 'diagnostic')
        actual = run_cases(self.probe, [{'state': before, 'data': [expected['write']['data']],
                                        'fill_pending': 0}])[0]
        for key in ('code', 'address', 'registers', 'command_pending'):
            self.assertEqual(actual[key], expected['state'][key])
        self.assertEqual(actual['fallback_calls'], 0)
        self.assertEqual(actual['diagnostic_calls'], 1)
        for bank in BANKS:
            self.assertEqual(hashlib.sha256(actual['memory'][bank]).hexdigest(),
                             expected['memory'][bank]['sha256'])

    def test_register_write_preserves_native_fill_command_and_md_fallback(self):
        fixture = json.loads(FIXTURE.read_text())
        case = next(case for case in fixture['cases']
                    if case['name'] == 'fill_register_write_between_command_data')
        before = case['steps'][1]['state']
        register, fill = case['steps'][2:4]
        self.assertEqual(register['write']['address'] & 31, 4)
        self.assertEqual(register['write']['data'] & 0xc000, 0x8000)
        commands = [(1, register['write']['data']), (0, fill['write']['data'])]
        rows = run_cases(self.probe, [{'state': before, 'commands': commands,
                                      'fill_pending': 0}])
        for actual, expected in zip(rows, (register, fill)):
            for key in ('code', 'address', 'registers', 'command_pending'):
                self.assertEqual(actual[key], expected['state'][key])
            for bank in BANKS:
                self.assertEqual(hashlib.sha256(actual['memory'][bank]).hexdigest(),
                                 expected['memory'][bank]['sha256'])
        self.assertEqual(rows[-1]['fallback_calls'], 0)
        ordinary = run_cases(self.probe, [{'state': before, 'commands': commands[:1],
                                          'mdp': 0}])[0]
        self.assertEqual(ordinary['code'], 0)
        self.assertEqual(ordinary['address'], 0)

    def test_fresh_original_execution_when_configured(self):
        path = os.environ.get('MDP_TRANSFER_ORACLE_JSON')
        if not path:
            self.skipTest('MDP_TRANSFER_ORACLE_JSON is not configured')
        self.compare(json.loads(Path(path).read_text()))


if __name__ == '__main__':
    unittest.main()

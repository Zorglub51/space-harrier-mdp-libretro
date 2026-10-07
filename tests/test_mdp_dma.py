"""Compare production MDP DMA/copy methods with synthetic original-ARM traces.

The native control-port steps supply the state at entry to handle_dma_bits.
The production dispatch prefix, transfer bodies, and VSRAM write helper are
compiled from the public patch. The bus callback returns synthetic values and
records every full source address, including the read preceding a diagnostic.
This probe does not claim to validate CPU scheduling or the whole control port.
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
from test_mdp_transfers import BANKS, BINARY_SHA256, FIXTURE

HANDLER_SHA256 = 'd07969110e42a6830564247764dfe5d780dc9205cf52036ceb18a5147bc2a55d'
HEADER_KEYS = ('code', 'address', 'command_pending', 'fill_pending',
               'diagnostic_calls', 'fallback_calls', 'data_fallback_calls', 'spin_calls')
HEADER_WORDS = len(HEADER_KEYS) + 64 + 1


def first_block(source, start):
    """Return a complete brace-delimited block, including its opening brace."""
    begin = source.index('{', start)
    depth, end = 1, begin + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[begin:end]


def probe_source():
    source = patched_fragments(PATCH.read_text(), 'src/devices/video/315_5313.cpp')
    bodies = '\n'.join(full_function(source, signature) for signature in (
        'void sega315_5313_device::mdp_dma_transfer()',
        'void sega315_5313_device::mdp_vram_copy()',
        'void sega315_5313_device::mdp_vsram_write(u16 address, u16 data)',
        'void sega315_5313_device::vdp_mdp_w(offs_t offset, u16 data, u16 mem_mask)',
    ))
    start = source.index('void sega315_5313_device::vdp_vsram_write(u16 data)')
    end = source.index('\n\t//logerror("Wrote to VSRAM', start)
    # The diff ends before this function's unchanged address increment. Compile
    # the actual modified dispatch prefix and supply that caller bookkeeping.
    bodies += '\n' + source[start:end] + '\n vdp_address_inc();\n}\n'
    start = source.index('void sega315_5313_device::handle_dma_bits()')
    branch = source.index('if (m_mdp_scaler)', start)
    # Compile the actual route; only the inherited ordinary-MD body is replaced.
    dispatch = (source[start:branch] + 'if (m_mdp_scaler)\n' +
                first_block(source, branch) + '\n ++fallback_calls;\n}\n')
    start = source.index('void sega315_5313_device::data_port_w(int data)')
    end = source.index('\n\t/*\n\t0000b : VRAM read', start)
    data_dispatch = source[start:end] + '\n ++data_fallback_calls;\n}\n'
    return r'''
#include <array>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <iostream>
#include <utility>
#include <vector>
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif
using u8=std::uint8_t;using u16=std::uint16_t;using u32=std::uint32_t;
using offs_t=std::uint32_t;
#define BIT(value, bit) (((value) >> (bit)) & 1U)
#define ACCESSING_BITS_0_7 ((mem_mask & 0x00ff) != 0)
#define ACCESSING_BITS_8_15 ((mem_mask & 0xff00) != 0)
struct attotime {static double from_nsec(double n){return n;}};
struct cpu_stub {unsigned calls=0;void spin_until_time(double){++calls;}unsigned pcbase(){return 0;}};
struct screen_stub {unsigned frame_number(){return 0;}};
class sega315_5313_device {
public:
 bool m_markvi_ready[3]{};
 void sh2_markvi_dma(u32,u32,u32,bool){} // Presentation observer; no DMA bus effects.
 bool m_mdp_scaler=true;
 u16 m_regs[64]{};
 u16 m_vdp_code=0,m_vdp_address=0,m_vram_fill_length=0;
 int m_command_pending=0,m_vram_fill_pending=0;
 unsigned diagnostic_calls=0,fallback_calls=0,data_fallback_calls=0;
 std::array<u16,65536> m_vram{};
 std::array<u16,128> m_cram{};
 std::array<u16,64> m_vsram{};
 u16 m_mdp_raster_cram[256][128]{};
 u8 m_mdp_raster_cram_set[256][128]{};
 cpu_stub cpu;cpu_stub* m_cpu68k=&cpu;
 screen_stub display;
 screen_stub& screen(){return display;}
 int get_scanline_counter(){return 0;}
 std::vector<std::pair<u32,u32>> reads;
 u16 mdp_dma_read_word(u32 source){
  const u32 value=0xbeef0000U|((source^(source>>16)^0xa55aU)&65535);
  reads.emplace_back(source,value);return u16(value);
 }
 void vram_w(u32 index,u16 data,u16 mask=0xffff){
  if(index>=32768)std::abort();
  m_vram[index]=(m_vram[index]&~mask)|(data&mask);
 }
 void write_cram_value(unsigned index,u16 data){
  if(index>=128)std::abort();
  m_cram[index]=data;
 }
 template<typename... Args>void logerror(const char*,Args...){++diagnostic_calls;}
 void mdp_dma_transfer();void mdp_vram_copy();void mdp_vsram_write(u16,u16);
 void vdp_mdp_w(offs_t,u16,u16);
 void vdp_w(offs_t,u16,u16){++data_fallback_calls;}
 void vdp_vsram_write(u16);
 void vdp_address_inc(){m_vdp_address=u16(m_vdp_address+m_regs[15]);}
 void handle_dma_bits();void data_port_w(int);
 void mdp_vram_fill(u16){std::abort();}
};
BODIES
DISPATCH
DATA_DISPATCH
void word(u32 v){for(unsigned i=0;i<4;++i)std::cout.put(char(v>>(i*8)));}
u16 seed_word(unsigned index,unsigned salt){
 return u16((index*2*37+salt)&255)|(u16(((index*2+1)*37+salt)&255)<<8);
}
void output_word(u16 v){std::cout.put(char(v));std::cout.put(char(v>>8));}
void output(sega315_5313_device& v){
 word(v.m_vdp_code);word(v.m_vdp_address);word(v.m_command_pending);
 word(v.m_vram_fill_pending);word(v.diagnostic_calls);word(v.fallback_calls);
 word(v.data_fallback_calls);word(v.cpu.calls);
 for(auto r:v.m_regs)word(r);
 word(u32(v.reads.size()));
 for(auto w:v.m_vram)output_word(w);
 for(auto w:v.m_cram)output_word(w);
 // Inverse rotation only. Do not make inconsistent seeded mirrors agree.
 for(unsigned j=0;j<64;++j)output_word(v.m_vsram[(j+62)&63]);
 for(auto r:v.reads){word(r.first);word(r.second);}
}
int main(){
#ifdef _WIN32
 if(_setmode(_fileno(stdout),_O_BINARY)==-1)return 5;
#endif
 unsigned mdp,code,address,command_pending,count;
 while(std::cin>>mdp>>code>>address>>command_pending>>count){
  sega315_5313_device v;v.m_mdp_scaler=mdp;v.m_vdp_code=u16(code);
  v.m_vdp_address=u16(address);v.m_command_pending=command_pending;
  for(auto& r:v.m_regs){unsigned x;if(!(std::cin>>x))return 2;r=u16(x);}
  for(unsigned i=0;i<v.m_vram.size();++i)v.m_vram[i]=seed_word(i,13);
  for(unsigned i=0;i<v.m_cram.size();++i)v.m_cram[i]=seed_word(i,71);
  for(unsigned i=0;i<64;++i)v.m_vsram[i]=seed_word((i+2)&63,149);
  for(unsigned i=0;i<count;++i){unsigned action,data;
   if(!(std::cin>>action>>data))return 3;
   v.reads.clear();
   if(action==0)v.handle_dma_bits();
   else if(action==1)v.data_port_w(data);
   else if(action==2)v.vdp_vsram_write(u16(data));
   else if((action&65535)==3)v.vdp_mdp_w((action>>16)/2,u16(data),0xffff);
   else if((action&65535)==5)v.vdp_mdp_w((action>>16)/2,u16(data),0xff00);
   else if((action&65535)==6)v.vdp_mdp_w((action>>16)/2,u16(data),0x00ff);
   else if(action==4)v.m_vdp_address=u16(data); // Native control-state boundary.
   else return 4;
   output(v);
  }
 }
 return std::cin.eof()?0:4;
}
'''.replace('BODIES', bodies).replace('DATA_DISPATCH', data_dispatch).replace('DISPATCH', dispatch)


def transfer_steps(fixture):
    """Reconstruct the completed command at the native transfer entry boundary."""
    result = []
    for case in fixture['cases']:
        if case['kind'] not in ('dma68k', 'copy', 'dispatch'):
            continue
        before, transfer = case['steps'][:2]
        data = transfer['write']['data']
        if transfer['write']['address'] & 31 not in (4, 6):
            raise AssertionError('transfer is not the command-completion write')
        state = dict(before['state'])
        if not state['command_pending']:
            raise AssertionError('missing first command word')
        state['code'] |= (data >> 2) & 0x3c
        state['address'] |= (data & 3) << 14
        state['command_pending'] = False
        result.append((case, state, transfer))
    return result


def run_cases(probe, requests):
    text = []
    for request in requests:
        state = request['state']; commands = request.get('commands', [(0, 0)])
        text.append(' '.join(map(str, [request.get('mdp', 1), state['code'],
                    state['address'], int(state['command_pending']), len(commands)] +
                    state['registers'] + [x for command in commands for x in command])))
    environment = os.environ.copy()
    environment.pop('MDP_NAMETAB', None)
    result = subprocess.run([str(probe)], input=('\n'.join(text) + '\n').encode(),
                            capture_output=True, check=True, timeout=30, env=environment)
    count = sum(len(r.get('commands', [(0, 0)])) for r in requests)
    rows, offset = [], 0
    for _ in range(count):
        header = struct.unpack_from('<' + 'I' * HEADER_WORDS, result.stdout, offset)
        row = dict(zip(HEADER_KEYS, header[:len(HEADER_KEYS)]))
        row['registers'] = list(header[len(HEADER_KEYS):-1])
        reads = header[-1]; offset += HEADER_WORDS * 4
        row['memory'] = {}
        for name, (size, _) in BANKS.items():
            row['memory'][name] = result.stdout[offset:offset + size]; offset += size
        trace = result.stdout[offset:offset + reads * 8]; offset += reads * 8
        if len(trace) != reads * 8:
            raise AssertionError('truncated production bus trace')
        row['bus_reads'] = [{'address': a, 'value': v} for a, v in struct.iter_unpack('<II', trace)]
        row['bus_sha256'] = hashlib.sha256(trace).hexdigest()
        rows.append(row)
    if offset != len(result.stdout):
        raise AssertionError('unexpected production state or memory output')
    return rows


class MdpDmaTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory();cls.addClassCleanup(cls.temporary.cleanup)
        directory = Path(cls.temporary.name);source = directory / 'mdp-dma-probe.cpp'
        source.write_text(probe_source())
        cls.probe = directory / ('mdp-dma-probe.exe' if os.name == 'nt' else 'mdp-dma-probe')
        subprocess.run(shlex.split(os.environ.get('CXX', 'c++')) + [
            '-std=c++17', '-Wall', '-Wextra', '-Werror', str(source), '-o', str(cls.probe),
        ], check=True)

    def compare(self, fixture, kind=None):
        self.assertEqual(fixture['binary_sha256'], BINARY_SHA256)
        self.assertEqual(fixture['handler_sha256'], HANDLER_SHA256)
        selected = [r for r in transfer_steps(fixture) if kind is None or r[0]['kind'] == kind]
        self.assertEqual(len(selected), {'dma68k': 36, 'copy': 18, 'dispatch': 5, None: 59}[kind])
        self.assertEqual(len({c['name'] for c, _, _ in selected}), len(selected))
        rows = run_cases(self.probe, [{'state': state} for _, state, _ in selected])
        for (case, before, expected), actual in zip(selected, rows):
            with self.subTest(case=case['name']):
                for key in ('code', 'address', 'command_pending', 'registers'):
                    self.assertEqual(actual[key], expected['state'][key], key)
                self.assertEqual(actual['fallback_calls'], 0)
                self.assertEqual(actual['data_fallback_calls'], 0)
                self.assertEqual(actual['diagnostic_calls'], int(expected['boundary'] == 'diagnostic'))
                for name in BANKS:
                    self.assertEqual(hashlib.sha256(actual['memory'][name]).hexdigest(),
                                     expected['memory'][name]['sha256'], name)
                reads = expected['bus_reads'];trace = actual['bus_reads']
                self.assertEqual(len(trace), reads['count'])
                self.assertEqual(trace[:8], reads['first'])
                self.assertEqual(trace[-1] if trace else None, reads['last'])
                self.assertEqual(actual['bus_sha256'], reads['sha256'])
                if expected['boundary'] == 'diagnostic':
                    # Reads and already completed writes survive the fault, but
                    # the local destination/length are not committed on failure.
                    if case['kind'] == 'dma68k':
                        self.assertGreater(len(trace), 0)
                    self.assertEqual(actual['address'], before['address'])
                    self.assertEqual(actual['registers'][19:24], before['registers'][19:24])

    def test_dma_memory_registers_and_bus_trace_match_original(self):
        self.compare(json.loads(FIXTURE.read_text()), 'dma68k')

    def test_copy_overlap_wrap_memory_and_state_match_original(self):
        self.compare(json.loads(FIXTURE.read_text()), 'copy')

    def test_native_dma_type_and_command_dispatch(self):
        self.compare(json.loads(FIXTURE.read_text()), 'dispatch')

    def test_vsram_shifted_backing_and_mirrors_match_original(self):
        fixture = json.loads(FIXTURE.read_text())
        cases = {case['name']: case for case in fixture['cases'] if case['kind'] == 'vsram_write'}
        self.assertEqual(len(cases), 3)
        for name, case in cases.items():
            steps = case['steps']
            if name == 'vsram_direct_mirrors':
                # Compile and execute the entire production direct decoder.
                before = dict(case['input'], command_pending=bool(case['input']['flags'] & 8))
                commands = [(3 | ((step['write']['address'] & 65535) << 16), step['write']['data'])
                            for step in steps]
                expected = steps
            else:
                before = steps[1]['state']
                commands = [(2, step['write']['data']) for step in steps[2:4]]
                expected = steps[2:4]
                if name == 'vsram_high_overrides_only_mirrors':
                    # Preserve the bank between writes; inject only the native
                    # completed command's address, without emulating control code.
                    commands += [(4, steps[5]['state']['address'])]
                    commands += [(2, step['write']['data']) for step in steps[6:8]]
                    expected += [None] + steps[6:8]
            rows = run_cases(self.probe, [{'state': before, 'commands': commands}])
            for actual, step in zip(rows, expected):
                if step is None:
                    continue
                with self.subTest(case=name, write=step['write']):
                    for key in ('code', 'address', 'command_pending', 'registers'):
                        self.assertEqual(actual[key], step['state'][key])
                    for bank in BANKS:
                        self.assertEqual(hashlib.sha256(actual['memory'][bank]).hexdigest(),
                                         step['memory'][bank]['sha256'])
                    self.assertEqual(actual['bus_reads'], [])

    def test_direct_vsram_byte_lanes_duplicate_the_selected_byte(self):
        fixture = json.loads(FIXTURE.read_text())
        native_bytes = [case for case in fixture['cases'] if case['kind'] == 'vsram_write8']
        self.assertEqual(len(native_bytes), 2)
        for case in native_bytes:
            before = dict(case['input'], command_pending=bool(case['input']['flags'] & 8))
            expected = case['steps'][0]
            write = expected['write']
            odd = write['address'] & 1
            action = (6 if odd else 5) | ((write['address'] & 0xfffe) << 16)
            value = write['data'] if odd else write['data'] << 8
            actual = run_cases(self.probe, [{'state': before, 'commands': [(action, value)]}])[0]
            with self.subTest(native_byte_case=case['name']):
                for key in ('code', 'address', 'command_pending', 'registers'):
                    self.assertEqual(actual[key], expected['state'][key])
                for bank in BANKS:
                    self.assertEqual(hashlib.sha256(actual['memory'][bank]).hexdigest(),
                                     expected['memory'][bank]['sha256'])
        case = next(c for c in fixture['cases'] if c['name'] == 'vsram_direct_mirrors')
        before = dict(case['input'], command_pending=bool(case['input']['flags'] & 8))
        for address in (0x200, 0x202, 0x27c, 0x27e):
            requests = [{'state': before, 'commands': [(action | (address << 16), value)]}
                        for action, value in ((3, 0xabab), (5, 0xab00), (6, 0x00ab))]
            rows = run_cases(self.probe, requests)
            with self.subTest(address=hex(address)):
                self.assertEqual(rows[0], rows[1])
                self.assertEqual(rows[0], rows[2])
                self.assertEqual(rows[0]['data_fallback_calls'], 0)
                self.assertEqual(rows[0]['address'], before['address'])
                self.assertEqual(rows[0]['code'], before['code'])
        for address in (0x1fe, 0x280):
            row = run_cases(self.probe, [{'state': before,
                                         'commands': [(3 | (address << 16), 0xabcd)]}])[0]
            self.assertEqual(row['data_fallback_calls'], 1)
            for bank, (size, salt) in BANKS.items():
                self.assertEqual(row['memory'][bank], bytes((i * 37 + salt) & 255 for i in range(size)))

    def test_ordinary_md_dispatch_stays_in_inherited_path(self):
        requests = [{'state': state, 'mdp': 0} for _, state, _ in transfer_steps(json.loads(FIXTURE.read_text()))]
        for request, actual in zip(requests, run_cases(self.probe, requests)):
            self.assertEqual(actual['fallback_calls'], 1)
            self.assertEqual(actual['diagnostic_calls'], 0)
            self.assertEqual(actual['bus_reads'], [])
            self.assertEqual(actual['spin_calls'], 0)
            for key in ('code', 'address', 'registers', 'command_pending'):
                self.assertEqual(actual[key], request['state'][key])
            for bank, (size, salt) in BANKS.items():
                self.assertEqual(actual['memory'][bank], bytes((i * 37 + salt) & 255 for i in range(size)))

    def test_copy_completion_cannot_be_reentered_by_another_data_write(self):
        case, before, first = next(r for r in transfer_steps(json.loads(FIXTURE.read_text()))
                                  if r[0]['name'] == 'copy_second_data_diagnostic')
        last = case['steps'][2]
        self.assertEqual(last['boundary'], 'diagnostic')
        rows = run_cases(self.probe, [{'state': before, 'commands': [(0, 0), (1, last['write']['data'])]}])
        self.assertEqual(rows[0]['code'], 0xff)
        self.assertEqual(rows[0]['data_fallback_calls'], 0)
        self.assertEqual(rows[1]['data_fallback_calls'], 1)
        self.assertEqual(rows[1]['memory'], rows[0]['memory'])
        self.assertEqual(rows[1]['bus_reads'], [])
        for key in ('code', 'address', 'registers', 'command_pending'):
            self.assertEqual(rows[1][key], last['state'][key])

    def test_fresh_original_execution_when_configured(self):
        path = os.environ.get('MDP_TRANSFER_ORACLE_JSON')
        if not path:
            self.skipTest('MDP_TRANSFER_ORACLE_JSON is not configured')
        self.compare(json.loads(Path(path).read_text()))

BUS_FIXTURE = Path(__file__).resolve().parent / 'fixtures/mdp_bus_m2.json'


def bus_probe_source():
    patch = PATCH.read_text()
    cpp = patched_fragments(patch, 'src/devices/video/315_5313.cpp')
    driver = patched_fragments(patch, 'src/mame/sega/megadriv.cpp')
    read = full_function(cpp, 'u16 sega315_5313_device::mdp_dma_read_word(u32 source)')
    mapping = next(line.strip() for line in driver.splitlines()
                   if '.share("megadrive_ram")' in line)
    reset = next(line.strip() for line in driver.splitlines()
                 if 'memset(m_megadrive_ram,' in line)
    return r'''
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <iostream>
#include <string>
#include <vector>
#ifdef _WIN32
#include <fcntl.h>
#include <io.h>
#endif
using u16=std::uint16_t;using u32=std::uint32_t;
struct map_entry {
 u32 begin=0,end=0,mask=0;std::string name;
 map_entry& ram(){return *this;}
 map_entry& mirror(u32 m){mask=m;return *this;}
 map_entry& share(const char* n){name=n;return *this;}
};
struct address_map {
 map_entry entry;
 map_entry& operator()(u32 begin,u32 end){entry.begin=begin;entry.end=end;return entry;}
};
struct shared_ram {
 std::vector<u16> words;
 operator void*(){return words.data();}
 std::size_t bytes()const{return words.size()*2;}
};
struct test_space {
 map_entry entry;shared_ram ram;std::vector<u16> rom;u32 last_address=0;
 void initialize(unsigned rom_size){
  address_map map;
  MAP_STATEMENT
  entry=map.entry;
  if(entry.name!="megadrive_ram"||entry.end<entry.begin)std::abort();
  ram.words.resize((entry.end-entry.begin+1)/2);
  for(unsigned i=0;i<ram.words.size();++i)ram.words[i]=u16(i*37+0x5678);
  rom.resize(rom_size/2);
  for(unsigned i=0;i<rom.size();++i)rom[i]=u16(i*11+(i>>15)*0x123+0x1234);
 }
 unsigned ram_index(u32 address)const{
  const u32 canonical=(address&0xffffff)&~entry.mask;
  if(canonical<entry.begin||canonical>entry.end)std::abort();
  return (canonical-entry.begin)/2;
 }
 u16 read_word(u32 address){
  last_address=address;
  if(address>=entry.begin)return ram.words[ram_index(address)];
  // Synthetic ROM callback from the native fixture, not MAME cartridge code.
  return rom[(address&(u32(rom.size()*2)-1))>>1];
 }
 void write_word(u32 address,u16 value){ram.words[ram_index(address)]=value;}
};
class sega315_5313_device {
public:test_space space;test_space* m_space68k=&space;u16 mdp_dma_read_word(u32);
};
READ_FUNCTION
void word(u32 v){for(unsigned i=0;i<4;++i)std::cout.put(char(v>>(8*i)));}
void bank(const std::vector<u16>& v){for(auto w:v){std::cout.put(char(w));std::cout.put(char(w>>8));}}
int main(){
#ifdef _WIN32
 if(_setmode(_fileno(stdout),_O_BINARY)==-1)return 5;
#endif
 unsigned operation,address,data,rom_size,count;
 while(std::cin>>operation>>address>>data>>rom_size>>count){
  sega315_5313_device v;v.space.initialize(rom_size);
  if(operation==1)v.space.write_word(address,u16(data));
  else if(operation==2){
   auto& m_megadrive_ram=v.space.ram;
   RESET_STATEMENT
  }
  else if(operation!=0)return 2;
  word(u32(v.space.ram.bytes()));word(v.space.entry.begin);word(v.space.entry.end);word(v.space.entry.mask);
  for(unsigned i=0;i<count;++i){unsigned source;if(!(std::cin>>source))return 3;
   word(v.mdp_dma_read_word(source));word(v.space.last_address);
  }
  bank(v.space.ram.words);bank(v.space.rom);
 }
 return std::cin.eof()?0:4;
}
'''.replace('MAP_STATEMENT', mapping).replace('RESET_STATEMENT', reset).replace('READ_FUNCTION', read)


def run_bus_cases(probe, requests):
    text = [' '.join(map(str, [r.get('operation', 0), r.get('address', 0), r.get('data', 0),
                              r.get('rom_size', 65536), len(r['reads'])] + r['reads']))
            for r in requests]
    result = subprocess.run([str(probe)], input=('\n'.join(text) + '\n').encode(),
                            capture_output=True, check=True, timeout=30)
    rows, offset = [], 0
    for request in requests:
        size, begin, end, mask = struct.unpack_from('<IIII', result.stdout, offset);offset += 16
        row = dict(size=size, begin=begin, end=end, mask=mask, reads=[])
        for _ in request['reads']:
            value, address = struct.unpack_from('<II', result.stdout, offset);offset += 8
            row['reads'].append({'value': value, 'address': address})
        row['ram'] = result.stdout[offset:offset + size];offset += size
        rom_size = request.get('rom_size', 65536)
        row['rom'] = result.stdout[offset:offset + rom_size];offset += rom_size
        rows.append(row)
    if offset != len(result.stdout):
        raise AssertionError('unexpected RAM-map probe output size')
    return rows


class MdpDmaBusTests(unittest.TestCase):
    """Compile the real read helper, RAM declaration, and reset statement.

    The address_map/share descriptor adapter checks the declared size and
    mirrors. It does not substitute for exercising MAME's full address_space.
    """

    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory();cls.addClassCleanup(cls.temporary.cleanup)
        directory = Path(cls.temporary.name);source = directory / 'mdp-bus-probe.cpp'
        source.write_text(bus_probe_source())
        cls.probe = directory / ('mdp-bus-probe.exe' if os.name == 'nt' else 'mdp-bus-probe')
        subprocess.run(shlex.split(os.environ.get('CXX', 'c++')) + [
            '-std=c++17', '-Wall', '-Wextra', '-Werror', str(source), '-o', str(cls.probe),
        ], check=True)

    def compare(self, fixture):
        self.assertEqual(fixture['binary_sha256'], BINARY_SHA256)
        self.assertEqual(fixture['read16']['sha256'],
                         '81c6316adfba6adbc493dde4145b958137a8ea9af03b690b081c17ba785a32df')
        reads = [case for case in fixture['cases'] if case['kind'] == 'read16']
        self.assertEqual(len(reads), 30)
        requests = [{'reads': [case['source']], 'rom_size': case['rom_size']} for case in reads]
        for case, actual in zip(reads, run_bus_cases(self.probe, requests)):
            with self.subTest(source=hex(case['source']), rom_size=case['rom_size']):
                self.assertEqual(actual['reads'][0]['value'], case['output']['result'])
                self.assertEqual(actual['size'], fixture['ram_size'])
                forwarded = actual['reads'][0]['address']
                if case['source'] < 0xe00000:
                    self.assertEqual(forwarded, case['source'])
                else:
                    self.assertGreaterEqual(forwarded, actual['begin'])
                    self.assertLessEqual(forwarded, actual['end'])
                    self.assertEqual(forwarded & 1, 0)
        # CPU writes are 24-bit. The three native host-only writes above FFFFFF
        # are intentionally not presented as tested MAME CPU behavior.
        writes = [case for case in fixture['cases'] if case['kind'] == 'write16'
                  and case['destination'] <= 0xffffff]
        self.assertEqual(len(writes), 5)
        requests = [{'operation': 1, 'address': c['destination'], 'data': c['data'],
                     'reads': [r['address'] for r in c['readbacks']]} for c in writes]
        for case, actual in zip(writes, run_bus_cases(self.probe, requests)):
            with self.subTest(destination=hex(case['destination'])):
                self.assertEqual([r['value'] for r in actual['reads']],
                                 [r['output']['result'] for r in case['readbacks']])
                self.assertEqual(hashlib.sha256(actual['ram']).hexdigest(), case['ram_sha256'])
                self.assertEqual(hashlib.sha256(actual['rom']).hexdigest(), case['rom_sha256'])

    def test_native_bus_results_and_production_ram_mapping(self):
        # ROM is an explicitly synthetic callback; size 380000 exercises native
        # mask semantics and is not a claim about the real cartridge loader.
        self.compare(json.loads(BUS_FIXTURE.read_text()))

    def test_reset_clears_both_mapped_ram_banks(self):
        before, after = run_bus_cases(self.probe, [
            {'reads': [0xfe0000, 0xff0000]},
            {'operation': 2, 'reads': [0xfe0000, 0xff0000, 0xfffffe]},
        ])
        self.assertEqual(before['size'], 131072)
        self.assertEqual(before['reads'][0]['value'], 0x5678)
        self.assertEqual(before['reads'][1]['value'], 0xd678)
        self.assertEqual(after['ram'], bytes(131072))
        self.assertEqual([r['value'] for r in after['reads']], [0, 0, 0])
        self.assertEqual(after['rom'], before['rom'])

    def test_fresh_original_bus_execution_when_configured(self):
        path = os.environ.get('MDP_BUS_ORACLE_JSON')
        if not path:
            self.skipTest('MDP_BUS_ORACLE_JSON is not configured')
        self.compare(json.loads(Path(path).read_text()))


if __name__ == '__main__':
    unittest.main()

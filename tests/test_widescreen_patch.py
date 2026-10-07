"""Authenticated viewport substitutions preserve native bounds when disabled."""
import os
from pathlib import Path
import shlex
import subprocess
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]

class WidescreenPatch(unittest.TestCase):
    def test_instruction_guards_and_piece_bounds(self):
        source=r'''
#include "sh_widescreen_patch.h"
#include "sh2_markvi.h"
#include <cassert>
#include <map>
using u16=std::uint16_t;using u32=std::uint32_t;
int main(){
 for(auto game:{sh_widescreen::profile::sh1,sh_widescreen::profile::sh2}){
  std::map<u32,u16> rom;
  const auto &pairs=game==sh_widescreen::profile::sh1?sh_widescreen::sh1_pairs:sh_widescreen::sh2_pairs;
  for(auto p:pairs){rom[p.address]=p.offset_opcode;rom[p.address+2]=0xffa0;rom[p.address+4]=p.limit_opcode;rom[p.address+6]=p.limit;}
  auto read=[&](u32 a){return rom[a];};
  assert(sh_widescreen::validate(read,game));
  auto old=rom;auto &sites=sh_widescreen::sites(game);
  for(auto p:sites){assert(rom[p.address]==p.original);rom[p.address]=p.wide;}
  assert(!sh_widescreen::validate(read,game));
  for(auto p:sites)rom[p.address]=p.original;
  assert(rom==old && sh_widescreen::validate(read,game));
  rom[pairs.back().address]^=1;assert(!sh_widescreen::validate(read,game));
 }
 for(auto game:{sh_widescreen::profile::sh1,sh_widescreen::profile::sh2}){
  std::map<u32,u16> rom;
  auto seed=[&](const auto &pairs){for(auto p:pairs){rom[p.address]=p.add_opcode;rom[p.address+2]=196;rom[p.address+4]=0x0c40+(p.add_opcode&7);rom[p.address+6]=392;rom[p.address+8]=p.branch_opcode;}};
  if(game==sh_widescreen::profile::sh1)seed(sh_widescreen::sh1_lifetime_pairs);else seed(sh_widescreen::sh2_lifetime_pairs);
  auto read=[&](u32 a){return rom[a];};assert(sh_widescreen::validate_lifetimes(read,game));
  for(auto site:sh_widescreen::lifetime_sites(game)){assert(rom[site.address]==site.original);rom[site.address]=site.wide;}
  assert(!sh_widescreen::validate_lifetimes(read,game));
  for(auto site:sh_widescreen::lifetime_sites(game))rom[site.address]=site.original;
  assert(sh_widescreen::validate_lifetimes(read,game));
  for(int x=-32768;x<32768;++x)assert((u16(x+249)<=498)==(x>=-249&&x<=249));
 }
 // Check both six-byte entry guards and the native Y/removal destinations.
 // A matching horizontal compare alone must not enable a different handler.
 for(auto game:{sh_widescreen::profile::sh1,sh_widescreen::profile::sh2}){
  const bool sh2=game==sh_widescreen::profile::sh2;
  const u32 entry=sh2?0x16ee6a:0x199bf4, keep=sh2?0x16ee70:0x199bfa, remove=sh2?0x16eeae:0x199c2e;
  std::map<u32,u16> rom{{entry,0x0c40},{entry+2,320},{entry+4,u16(sh2?0x623e:0x6234)},
   {keep,0x0c41},{keep+2,210},{keep+4,u16(sh2?0x6238:0x622e)},
   {remove,0x5339},{remove+2,0xff},{remove+4,u16(sh2?0x38a6:0x40a6)}};
  auto read=[&](u32 a){return rom[a];};
  assert(sh_widescreen::validate_projectiles(read,game));
  auto original=rom;
  for(auto p:original){rom[p.first]^=1;assert(!sh_widescreen::validate_projectiles(read,game));rom=original;}
  const auto &jump=sh_widescreen::projectile_jump_sites(game);
  assert(jump.size()==3 && jump[0].address==entry && jump[0].wide==0x4ef9);
  assert(((u32(jump[1].wide)<<16)|jump[2].wide)==sh_widescreen::projectile_stub_address);
  for(auto p:jump){assert(p.original==read(p.address));rom[p.address]=p.wide;}
  assert(!sh_widescreen::validate_projectiles(read,game));
  const auto &stub=sh_widescreen::projectile_stub_words(game);
  assert(stub.size()==17 && stub[0]==0x48e7 && stub[1]==0x2040); // save D2/A1
  assert(stub[8]==0x4cdf && stub[9]==0x0204); // restore same full registers
  assert(stub[2]==0x3240 && stub[3]==0x43e9 && stub[4]==53); // MOVEA/LEA preserve X
  assert(stub[6]==0x0c42 && stub[7]==426 && stub[10]==0x6206);
  assert(stub[11]==0x4ef9 && ((u32(stub[12])<<16)|stub[13])==keep);
  assert(stub[14]==0x4ef9 && ((u32(stub[15])<<16)|stub[16])==remove);
 }
 // The full 16-bit domain catches a sign/wrap error at either new edge.
 for(int x=-32768;x<32768;++x){
  assert((u16(x+53)<=426)==(x>=-53&&x<=373));
  assert((u16(x)<=320)==(x>=0&&x<=320));
 }
 std::map<u32,u16> mem;
 auto put=[&](u32 a,u32 v){mem[a]=u16(v>>16);mem[a+2]=u16(v);};
 put(0x13b78e,0xff3542);put(0xff38f2,0xff5000);put(0xff501c,0x1000);
 mem[0xff502a]=4;mem[0x100a]=0x100;put(0x100c,0x2000);
 auto read=[&](u32 a){return mem[a];};std::vector<sh2_markvi::sprite> pieces;
 for(int x:{42,43,95,96,447,448,500,501}){
  mem[0xff500c]=u16(x-128);
  assert(sh2_markvi::build(read,pieces,false));assert(!pieces.empty()==(x>=96&&x<=447));
  assert(sh2_markvi::build(read,pieces,true));assert(!pieces.empty()==(x>=43&&x<=500));
 }
}
'''
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'probe.cpp';p.write_text(source);exe=Path(tmp)/'probe'
            subprocess.run(shlex.split(os.environ.get('CXX','c++'))+['-std=c++17','-Wall','-Wextra','-Werror','-I',str(ROOT/'src/markv'),str(p),'-o',str(exe)],check=True)
            subprocess.run([str(exe)],check=True)

if __name__=='__main__':unittest.main()

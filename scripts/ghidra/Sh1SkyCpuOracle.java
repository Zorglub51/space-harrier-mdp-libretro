// Execute the original M2 68000 engine, SH1 sky code and native line scheduler.
// @category SpaceHarrier
// Usage: -postScript Sh1SkyCpuOracle.java output.json original.smp ram-64k.bin
// Requires the authenticated private ARM executable, ROM and a big-endian RAM
// snapshot. No emulator/game code or RAM is exported. The report is private.
//
// This is an isolated sky/IRQ experiment, NOT a full M2 boot or video recording.
// The captured state supplies scene parameters and generated IRQ code scaffolds;
// the palette immediates are rebuilt by the original ROM on the original CPU.
// The background workload is a synthetic BRA-to-self loop. V IRQs, sound, pixel
// composition and presentation are excluded. The original CPU interpreter,
// opcode-table constructor, IRQ query/ack, frame clock, H counter, memory bus
// and direct CRAM writes execute. No CPU instruction or IRQ is stubbed.
// No game accelerator is enabled; none targets the executed sky routines.

import ghidra.app.script.GhidraScript;
import ghidra.app.plugin.processors.sleigh.SleighLanguage;
import ghidra.pcode.emu.*;
import ghidra.pcode.exec.PcodeExecutorStatePiece.Reason;
import ghidra.program.model.lang.*;
import ghidra.program.model.mem.MemoryBlock;
import java.math.BigInteger;
import java.nio.file.*;
import java.util.*;
import java.security.MessageDigest;
import com.google.gson.GsonBuilder;
public class Sh1SkyCpuOracle extends GhidraScript {
 private static final String BINARY_SHA="2374ddca2241d2a040f587a1e86359c3d3d5f1dc93e566588b35e15bee73178f";
 private byte[] romBytes, ramBytes;
 PcodeEmulator m;PcodeThread<byte[]> t;long heap=0x10000000L;long steps=0;long cpu;long guestStop=-1;long owner,bus,irq,vdp,cram,ram,rom,desc;boolean record=false;List<Object> rows=new ArrayList<>(),writes=new ArrayList<>();
 byte[] le(long v,int n){byte[]b=new byte[n];for(int i=0;i<n;i++)b[i]=(byte)(v>>>(i*8));return b;}
 void put(long a,byte[]b){m.getSharedState().setVar(toAddr(a),b.length,true,b);}
 byte[] get(long a,int n){return m.getSharedState().getVar(toAddr(a),n,true,Reason.INSPECT);}
 void w(long a,long v,int n){put(a,le(v,n));}
 long r(long a,int n){byte[]b=get(a,n);long v=0;for(int i=0;i<n;i++)v|=((long)b[i]&255)<<(i*8);return v;}
 void reg(String n,long v){Register rr=currentProgram.getRegister(n);t.getState().setVar(rr,le(v,rr.getMinimumByteSize()));}
 long reg(String n){byte[]b=t.getState().getVar(currentProgram.getRegister(n),Reason.INSPECT);long v=0;for(int i=0;i<b.length;i++)v|=((long)b[i]&255)<<(i*8);return v&0xffffffffL;}
 void ret(){t.overrideContext(t.getContext().combineValues(new RegisterValue(currentProgram.getRegister("TMode"),BigInteger.valueOf(reg("lr")&1))));t.overrideCounter(toAddr(reg("lr")&~1L));}
 long alloc(int n){if(n<1||n>0x1000000)throw new IllegalArgumentException("Allocation size "+n);long a=heap;heap+=(n+15)&~15;put(a,new byte[n]);return a;}
 boolean stub(long pc)throws Exception{
  if(pc==0x6752c&&reg("r2")==guestStop){w(cpu+0x18,guestStop,4);reg("r0",reg("r1"));ret();return true;}

  if(pc==0xc1e24){if(record)rows.add(obj("line",(int)reg("r1"),"cram",r(cram,2)));ret();return true;}
  if(pc==0xa7104){ret();return true;}
  if(pc==0xc2ca8&&record)writes.add(obj("line",(int)r(vdp+0x78,4),"address",reg("r1"),"value",reg("r2"),"cycle",r(cpu+0x70,4)));

  if(pc==0x9e8d4||pc==0x9e90c||pc==0x7adec){reg("r0",alloc((int)reg("r0")));ret();return true;}
  if(pc==0x9e810){ret();return true;}
  if(pc==0x265e8){byte[]b=new byte[(int)reg("r2")];Arrays.fill(b,(byte)reg("r1"));if(b.length>0)put(reg("r0"),b);ret();return true;}
  if(pc==0x26bfc){int n=(int)reg("r2");if(n>0)put(reg("r0"),get(reg("r1"),n));ret();return true;}
  if(pc>=0x260c0&&pc<0x27038)throw new IllegalStateException("Unexpected PLT "+Long.toHexString(pc));
  return false;
 }
 long call(long entry,long...args)throws Exception {
  for(int i=0;i<args.length;i++)reg("r"+i,args[i]);reg("sp",0x30010000);reg("lr",0x40000001);
  RegisterValue c=new RegisterValue(currentProgram.getLanguage().getContextBaseRegister(),BigInteger.ZERO);t.overrideContext(c.combineValues(new RegisterValue(currentProgram.getRegister("TMode"),BigInteger.ONE)));t.overrideCounter(toAddr(entry));
  long start=steps;
  while(t.getCounter().getOffset()!=0x40000000L){
   long pc=t.getCounter().getOffset();if(++steps-start>10000000)throw new IllegalStateException("Step limit "+t.getCounter());
   if(steps%500000==0)println("steps="+steps+" pc="+t.getCounter());
   monitor.checkCancelled();if(!stub(pc))t.stepInstruction();
  }
  return reg("r0");
 }
 static Map<String,Object> obj(Object...v){Map<String,Object>x=new LinkedHashMap<>();for(int i=0;i<v.length;i+=2)x.put((String)v[i],v[i+1]);return x;}
 byte[] swapped(byte[]b){byte[]c=b.clone();for(int i=0;i<c.length;i+=2){c[i]=b[i+1];c[i+1]=b[i];}return c;}
 long guest32(long a){long p=ram+(a&0x1ffff);return (r(p,2)<<16)|r(p+2,2);}
 void guest32(long a,long v){long p=ram+(a&0x1ffff);w(p,v>>>16,2);w(p+2,v,2);}
 void prepare()throws Exception {
  owner=alloc(0x100);bus=alloc(0x40);irq=alloc(0x40);vdp=alloc(0x400);cram=alloc(0x100);ram=alloc(0x20000);desc=alloc(0x40);
  byte[]b=romBytes;rom=alloc(b.length);put(rom,swapped(b));
  w(owner+8,ram,4);w(owner+12,rom,4);w(owner+16,b.length,4);w(owner+0x18,bus,4);w(owner+0x1c,cpu,4);w(owner+0x20,vdp,4);
  w(bus+8,0xc0f75,4);w(bus+12,0xc086d,4);w(bus+0x1c,owner,4);
  w(irq,0xc1059,4);w(irq+4,0xc13dd,4);w(irq+12,vdp,4);
  w(cpu+4,bus,4);w(cpu+8,irq,4);
  for(int page=0;page<256;page++){
   long ptr=r(cpu+0x1cc,4);
   if(page*65536<b.length)ptr=rom+page*65536L;
   if(page>=0xe0)ptr=ram+(page%2)*65536L;
   w(cpu+0x1d0+page*4,ptr,4);w(cpu+0x9d0+page*4,ptr,4);
   if(page>=0xe0)w(cpu+0x5d0+page*4,ptr,4);
  }
  w(vdp,cram,4);w(vdp+0x10,bus,4);w(vdp+0x14,0x10,1);w(vdp+0x1e,1,1);w(vdp+0x60,474,4);w(vdp+0x64,240,4);w(vdp+0x68,320,4);w(vdp+0x6c,224,4);w(vdp+0x74,desc,4);
  w(desc+12,948,4);w(desc+16,0x21000000L,4);
 }
 Object sky(int phase)throws Exception{
  put(ram+65536,swapped(ramBytes));
  w(ram+0x1eff0,0x60fe,2);guest32(0xffff00,0xffeff0);w(ram+0x1406c,phase,2);
  w(cpu+0x14,0,4);w(cpu+0x18,0x142b2e,4);w(cpu+0x1c,0x2000,4);w(cpu+0x64,0xffff00,4);w(vdp+0x58,0,4);
  // Execute the original palette-program builder, not captured palette immediates.
  long savedPhase=r(ram+0x1406c,2);long offset=(short)r(ram+0x14068,2);
  w(cpu+0x18,0x142d22,4);w(cpu+0x28,offset*2,4);w(cpu+0x2c,offset,4);w(cpu+0x50,guest32(0xff4060),4);w(cpu+0x54,guest32(0xff4064),4);
  guestStop=0x142d80;call(0x66750,cpu,200000);guestStop=-1;
  if(r(cpu+0x18,4)!=0x142d80)throw new IllegalStateException("Builder stop");
  w(cpu+0x18,0x142b2e,4);w(ram+0x1406c,savedPhase,2);call(0x66750,cpu,1000);
  if(r(cpu+0x18,4)!=0xffeff0)throw new IllegalStateException("Setup did not return "+Long.toHexString(r(cpu+0x18,4)));
  println("PHASE="+phase+" initial="+Long.toHexString(r(cram,2)));
  rows=new ArrayList<>();writes=new ArrayList<>();record=true;
  reg("r4",owner);reg("r5",7);reg("r7",0x24924925L);reg("r8",0);reg("r9",0);reg("sp",0x30010000);reg("lr",0x40000001);t.overrideCounter(toAddr(0xc06fc));
  long start=steps;
  while(t.getCounter().getOffset()!=0xc0756){
   long pc=t.getCounter().getOffset();if(++steps-start>2000000)throw new IllegalStateException("Frame step limit "+t.getCounter());
   monitor.checkCancelled();
   if(!stub(pc))t.stepInstruction();
  }
  if(reg("r8")!=262||rows.size()!=232||writes.size()!=112)throw new IllegalStateException("Incomplete native frame");
  for(int i=0;i<rows.size();i++)if(((Number)((Map<?,?>)rows.get(i)).get("line")).intValue()!=i-8)throw new IllegalStateException("Native line sequence");
  for(int i=0;i<writes.size();i++){
   Map<?,?>e=(Map<?,?>)writes.get(i);
   if(((Number)e.get("line")).intValue()!=2*i+1||((Number)e.get("address")).longValue()!=0xc00400L)throw new IllegalStateException("Native CRAM write sequence");
  }
  record=false;println("FRAME phase="+phase+" rows="+rows.size()+" writes="+writes.size()+" steps="+(steps-start)+" pc="+t.getCounter());
  return obj("input_phase",phase,"output_phase",r(ram+0x1406c,2),"rows",rows,"writes",writes,"steps",steps-start);
 }
 private String hash(byte[]data,String kind)throws Exception{
  StringBuilder s=new StringBuilder();for(byte b:MessageDigest.getInstance(kind).digest(data))s.append(String.format("%02x",b&255));return s.toString();
 }
 public void run()throws Exception {
  if(getScriptArgs().length!=3)throw new IllegalArgumentException("usage: output.json original.smp ram-64k.bin");
  if(!BINARY_SHA.equals(currentProgram.getExecutableSHA256()))throw new IllegalStateException("Binary hash");
  romBytes=Files.readAllBytes(Path.of(getScriptArgs()[1]));ramBytes=Files.readAllBytes(Path.of(getScriptArgs()[2]));
  if(!hash(romBytes,"SHA-1").equals("e87e9338d7842db68a7a1e77bd5fc5b2bc8b2b72"))throw new IllegalArgumentException("Original SH1 ROM required");
  if(ramBytes.length!=65536)throw new IllegalArgumentException("Expected 64 KiB big-endian FF0000..FFFFFF RAM");
  m=new PcodeEmulator((SleighLanguage)currentProgram.getLanguage());t=m.newThread();
  for(MemoryBlock b:currentProgram.getMemory().getBlocks())if(b.isInitialized()){
   byte[]data=new byte[(int)b.getSize()];currentProgram.getMemory().getBytes(b.getStart(),data);put(b.getStart().getOffset(),data);
  }
  put(0x30000000,new byte[0x20000]);for(int i=0;i<13;i++)reg("r"+i,0);for(int i=0;i<32;i++)reg("d"+i,0);
  if(r(0x431d48,4)!=0x66751)throw new IllegalStateException("Expected relocated m68k_3 vtable");
  try {
   cpu=call(0x668e0,0,0,0,0);prepare();List<Object>cases=new ArrayList<>();cases.add(sky(0));cases.add(sky(1));
   Path output=Path.of(getScriptArgs()[0]);Files.createDirectories(output.toAbsolutePath().getParent());
   Files.writeString(output,new GsonBuilder().setPrettyPrinting().create().toJson(obj(
    "schema",1,"binary_sha256",BINARY_SHA,"rom_sha1",hash(romBytes,"SHA-1"),"ram_sha256",hash(ramBytes,"SHA-256"),
    "engine","Ghidra PcodeEmulator, original ARM m68k_3 CPU and native MDP line scheduler",
    "boundary","Isolated original sky builder 142D22..142D80, updater 142B2E and generated IRQ programs; native CPU constructor 668E0, executor 66750, frame loop C06FC..C0754, IRQ query/ack and CRAM writes. Captured scene state; synthetic idle guest outside IRQ; sound and pixel renderer intercepted; V IRQ disabled; no game accelerator or presentation.",
    "steps",steps,"cases",cases))+"\n");
   println("PASS two native sky phases, 262 slices and 112 H IRQ writes each");
  }catch(Exception ex){println("FAILED pc="+t.getCounter()+" steps="+steps);throw ex;}
 }
}

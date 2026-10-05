// Run the original MDP line loop with a synthetic CPU-slice write.
// Usage: -postScript MdpLineClockOracle.java /absolute/output.json
// Import m2engage without analysis. No game data or binary code is exported.
// @category SpaceHarrier
import ghidra.app.script.GhidraScript;
import ghidra.app.plugin.processors.sleigh.SleighLanguage;
import ghidra.pcode.emu.PcodeEmulator;
import ghidra.pcode.emu.PcodeThread;
import ghidra.pcode.exec.PcodeExecutorStatePiece.Reason;
import ghidra.program.model.lang.Register;
import ghidra.program.model.lang.RegisterValue;
import com.google.gson.GsonBuilder;
import java.math.BigInteger;
import java.nio.file.*;
import java.util.*;
public class MdpLineClockOracle extends GhidraScript {
 private PcodeEmulator machine; private PcodeThread<byte[]> thread;
 private static final long OWNER=0x10000000L,CTX=0x11000000L,CRAM=0x12000000L,DESC=0x13000000L,STACK=0x20001000L;
 private byte[] le(long v,int n){byte[] b=new byte[n];for(int i=0;i<n;i++)b[i]=(byte)(v>>>(i*8));return b;}
 private void reg(String n,long v){Register r=currentProgram.getRegister(n);thread.getState().setVar(r,le(v,r.getMinimumByteSize()));}
 private long reg(String n){byte[] b=thread.getState().getVar(currentProgram.getRegister(n),Reason.INSPECT);long v=0;for(int i=0;i<b.length;i++)v|=((long)b[i]&255)<<(i*8);return v&0xffffffffL;}
 private void w(long a,long v,int n){machine.getSharedState().setVar(toAddr(a),n,true,le(v,n));}
 private long r(long a,int n){byte[] b=machine.getSharedState().getVar(toAddr(a),n,true,Reason.INSPECT);long v=0;for(int i=0;i<n;i++)v|=((long)b[i]&255)<<(i*8);return v;}
 private void ret(){thread.overrideCounter(toAddr(reg("lr")&~1L));}
 private static Map<String,Object> obj(Object...v){Map<String,Object> m=new LinkedHashMap<>();for(int i=0;i<v.length;i+=2)m.put((String)v[i],v[i+1]);return m;}
 public void run()throws Exception {
  if(getScriptArgs().length!=1)throw new IllegalArgumentException("usage: output.json");
  String sha="2374ddca2241d2a040f587a1e86359c3d3d5f1dc93e566588b35e15bee73178f";
  if(!sha.equalsIgnoreCase(currentProgram.getExecutableSHA256()))throw new IllegalArgumentException("hash");
  if(currentProgram.getMemory().locateAddressesForFileOffset(0xb0644).get(0).getOffset()!=0xc0644)throw new IllegalArgumentException("mapping");
  machine=new PcodeEmulator((SleighLanguage)currentProgram.getLanguage());thread=machine.newThread();
  byte[] code=new byte[0x3398-0x644];currentProgram.getMemory().getBytes(toAddr(0xc0644),code);machine.getSharedState().setVar(toAddr(0xc0644),code.length,true,code);
  for(long a:new long[]{OWNER,CTX,CRAM,DESC,STACK-0x200})machine.getSharedState().setVar(toAddr(a),0x400,true,new byte[0x400]);
  w(OWNER+0x20,CTX,4);w(OWNER+0x1c,0x30000000,4);w(OWNER+0x24,0x31000000,4);
  w(CTX,CRAM,4);w(CTX+0x60,474,4);w(CTX+0x64,240,4);w(CTX+0x68,320,4);w(CTX+0x6c,224,4);w(CTX+0x74,DESC,4);w(CTX+0x1e,1,1);
  w(DESC+12,948,4);w(DESC+16,0x14000000,4);w(CRAM+0x62,0xbeef,2);
  for(int i=0;i<13;i++)reg("r"+i,0);
  // Seed the original frame-loop registers immediately before C06FC.
  // Native slices37..40 cover visible lines-1..2; CPU and sound are explicit stubs.
  reg("r4",OWNER);reg("r5",7);reg("r7",0x24924925L);reg("r8",37);reg("sp",STACK);reg("lr",0x40000001);
  thread.overrideCounter(toAddr(0xc06fc));
  RegisterValue c=new RegisterValue(currentProgram.getLanguage().getContextBaseRegister(),BigInteger.ZERO);thread.overrideContext(c.combineValues(new RegisterValue(currentProgram.getRegister("TMode"),BigInteger.ONE)));
  List<Object> events=new ArrayList<>();long pendingCycles=-1;int steps=0;
  while(steps++<10000){
   monitor.checkCancelled();long pc=thread.getCounter().getOffset();
   if(pc==0xc06fc&&reg("r8")==41)break;
   if(pc==0xc1e24){events.add(obj("event","render","native_slice",reg("r8"),"visible_line",(int)reg("r1"),"cram49",r(CRAM+0x62,2)));ret();continue;}
   if(pc==0x95018){pendingCycles=reg("r1");long value=0x100+(reg("r8")-37)*0x222;events.add(obj("event","cpu_slice_write","native_slice",reg("r8"),"requested_cycles",pendingCycles,"value",value));reg("r0",CTX);reg("r1",0xc00462);reg("r2",value);thread.overrideCounter(toAddr(0xc2ca8));continue;}
   if(pc==0xc2d5c&&pendingCycles>=0){events.add(obj("event","native_write_complete","native_slice",reg("r8"),"cram49",r(CRAM+0x62,2)));reg("r0",pendingCycles);pendingCycles=-1;}
   if(pc==0xa7104){ret();continue;}
   thread.stepInstruction();
  }
  if(steps>=10000)throw new IllegalStateException("step limit");
  if(events.size()!=12)throw new IllegalStateException("event count "+events.size());
  long previous=0xbeef;
  for(int slice=0;slice<4;slice++) {
   Map<?,?> render=(Map<?,?>)events.get(slice*3), cpu=(Map<?,?>)events.get(slice*3+1), write=(Map<?,?>)events.get(slice*3+2);
   long value=0x100+slice*0x222;
   if(!"render".equals(render.get("event")) || ((Number)render.get("visible_line")).intValue()!=slice-1 || ((Number)render.get("cram49")).longValue()!=previous)
    throw new IllegalStateException("Unexpected rendered line/colour at slice "+slice);
   if(!"cpu_slice_write".equals(cpu.get("event")) || ((Number)cpu.get("value")).longValue()!=value || !"native_write_complete".equals(write.get("event")) || ((Number)write.get("cram49")).longValue()!=value)
    throw new IllegalStateException("Unexpected CPU-slice write at slice "+slice);
   previous=value;
  }
  Files.writeString(Path.of(getScriptArgs()[0]),new GsonBuilder().setPrettyPrinting().create().toJson(obj("schema",1,"binary_sha256",sha,"engine","Ghidra PcodeEmulator ARM p-code","ghidra_version",ghidra.framework.Application.getApplicationVersion(),"boundary","Original C06FC..C0754 frame loop, C32C8/C3314 scheduler and C2CA8 direct CRAM write; CPU execution replaced with one synthetic native CRAM write per slice, sound and raster pixel routine intercepted","events",events,"steps",steps))+"\n");
  println("PASS native frame-loop render/write ordering, four slices");
 }
}

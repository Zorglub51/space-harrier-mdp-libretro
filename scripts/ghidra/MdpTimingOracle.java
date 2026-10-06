// Execute original MDP IRQ query/acknowledge, line counter and frame budget on synthetic inputs.
// Usage: -postScript MdpTimingOracle.java /absolute/output.json
// IRQ tests execute original code; frame-budget tests stub CPU, sound and line scheduler.
// No game assets are required beyond the private original m2engage program.
// @category SpaceHarrier
import ghidra.app.script.GhidraScript;
import ghidra.app.plugin.processors.sleigh.SleighLanguage;
import ghidra.pcode.emu.PcodeEmulator;
import ghidra.pcode.emu.PcodeThread;
import ghidra.pcode.exec.PcodeExecutorStatePiece.Reason;
import ghidra.program.model.lang.*;
import com.google.gson.GsonBuilder;
import java.math.BigInteger;
import java.nio.file.*;
import java.util.*;
import java.security.MessageDigest;
public class MdpTimingOracle extends GhidraScript {
 private PcodeEmulator machine;private PcodeThread<byte[]> thread;
 private static final long CTX=0x11000000,OWNER=0x10000000,STACK=0x20001000,STOP=0x40000000;
 private byte[] le(long v,int n){byte[] b=new byte[n];for(int i=0;i<n;i++)b[i]=(byte)(v>>>(8*i));return b;}
 private void reg(String n,long v){Register r=currentProgram.getRegister(n);thread.getState().setVar(r,le(v,r.getMinimumByteSize()));}
 private long reg(String n){byte[] b=thread.getState().getVar(currentProgram.getRegister(n),Reason.INSPECT);long v=0;for(int i=0;i<b.length;i++)v|=((long)b[i]&255)<<(8*i);return v&0xffffffffL;}
 private void w(long a,long v,int n){machine.getSharedState().setVar(toAddr(a),n,true,le(v,n));}
 private long r(long a,int n){byte[] b=machine.getSharedState().getVar(toAddr(a),n,true,Reason.INSPECT);long v=0;for(int i=0;i<n;i++)v|=((long)b[i]&255)<<(8*i);return v;}
 private static Map<String,Object> obj(Object...v){Map<String,Object> m=new LinkedHashMap<>();for(int i=0;i<v.length;i+=2)m.put((String)v[i],v[i+1]);return m;}
 private static final String[] HASHES={"c57ee366dc95b415ba5cdf0e22f133997ce1a865b03aa76d1165db3fc437fb37","bb46622e42f7b0dd89c0da47f0cb272b5798b9ae43d784269ba768914dccbd22","9210523dff1b9b73e2935429214e66cce797073441145a09cb6b68f78ca11a92","75ed82ea15e4e0888ecbb3f350ffd42bb9ef89d962fb780c1686440d8a67055f"};
 private void init()throws Exception{
  machine=new PcodeEmulator((SleighLanguage)currentProgram.getLanguage());thread=machine.newThread();
  int rangeIndex=0;
  for(long[]range:new long[][]{{0xc0644,0xc075c},{0xc1058,0xc1084},{0xc13dc,0xc1430},{0xc3314,0xc3398}}){byte[] b=new byte[(int)(range[1]-range[0])];currentProgram.getMemory().getBytes(toAddr(range[0]),b);String actual=HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(b));if(!HASHES[rangeIndex++].equals(actual))throw new IllegalStateException("Original code hash mismatch");machine.getSharedState().setVar(toAddr(range[0]),b.length,true,b);}
  for(long a:new long[]{OWNER,CTX,STACK-0x400})machine.getSharedState().setVar(toAddr(a),0x800,true,new byte[0x800]);
  for(int i=0;i<13;i++)reg("r"+i,0);reg("sp",STACK);reg("lr",STOP|1);for(String f:new String[]{"CY","ZR","NG","OV","TB","ISAModeSwitch"})if(currentProgram.getRegister(f)!=null)reg(f,0);
  RegisterValue c=new RegisterValue(currentProgram.getLanguage().getContextBaseRegister(),BigInteger.ZERO);thread.overrideContext(c.combineValues(new RegisterValue(currentProgram.getRegister("TMode"),BigInteger.ONE)));
  w(CTX+0x6c,224,4);
 }
 private void jump(long a){reg("lr",STOP|1);thread.overrideCounter(toAddr(a));}
 private void ret(){thread.overrideCounter(toAddr(reg("lr")&~1L));}
 private String runCall(long a)throws Exception{jump(a);for(int n=0;n<1000;n++){monitor.checkCancelled();long p=thread.getCounter().getOffset();if(p==STOP)return "return";if(p==0x9e818)return "diagnostic";thread.stepInstruction();}throw new IllegalStateException("limit");}
 private long query()throws Exception{reg("r1",CTX);if(!runCall(0xc1058).equals("return"))throw new IllegalStateException("query");return reg("r0");}
 public void run()throws Exception{
  if(getScriptArgs().length!=1)throw new IllegalArgumentException("Expected output JSON path");
  String sha="2374ddca2241d2a040f587a1e86359c3d3d5f1dc93e566588b35e15bee73178f";if(!sha.equals(currentProgram.getExecutableSHA256()))throw new IllegalStateException("sha");
  List<Object> queryCases=new ArrayList<>(),ackCases=new ArrayList<>(),lines=new ArrayList<>(),frames=new ArrayList<>();
  for(int f:new int[]{0,1,4,5,0x20,0x21,0x24,0x25})for(int en:new int[]{0,1,2,3}){
   init();w(CTX+0x14,(en&1)!=0?0x10:0,1);w(CTX+0x15,(en&2)!=0?0x20:0,1);w(CTX+0x58,0xa5000000L|f,4);long level=query();queryCases.add(obj("flags",0xa5000000L|f,"enables",en,"level",level,"after_flags",r(CTX+0x58,4)));
   reg("r2",CTX);String b=runCall(0xc13dc);ackCases.add(obj("flags_before_ack",0xa5000000L|f,"flags_actual_before_ack",((Map<?,?>)queryCases.get(queryCases.size()-1)).get("after_flags"),"enables",en,"boundary",b,"after_flags",r(CTX+0x58,4)));
  }
  for(int reload:new int[]{0,1,2,255}){
   init();w(CTX+0x1e,reload,1);w(CTX+0x14,0,1);w(CTX+0x58,0x30,4);List<Object> trace=new ArrayList<>();
   for(int y=0;y<8;y++){reg("r0",CTX);reg("r1",y+38);String b=runCall(0xc3314);if(!b.equals("return"))throw new IllegalStateException("clock");long flags=r(CTX+0x58,4);w(CTX+0x14,0x10,1);long irq=query();w(CTX+0x14,0,1);trace.add(obj("line",y,"counter",r(CTX+0x5f,1),"flags_before_enable",flags,"irq_if_enabled_now",irq));}
   lines.add(obj("reload",reload,"never_acknowledge",true,"trace",trace));
  }
  init();w(CTX+0x58,0x30,4);w(CTX+0x1e,255,1);w(CTX+0x15,0x20,1);long blankIrq=query();w(CTX+0x15,0,1);reg("r0",CTX);reg("r1",38);runCall(0xc3314);long lineZeroFlags=r(CTX+0x58,4);w(CTX+0x15,0x20,1);long delayedVirq=query();
  Map<String,Object> vertical=obj("input_pending_flags",0x30,"irq_during_blank_if_enabled",blankIrq,"never_acknowledge",true,"line0_flags_before_enable",lineZeroFlags,"irq_after_enable_at_line0",delayedVirq);
  for(int quantum:new int[]{1,4}){
   init();w(OWNER+0x20,CTX,4);reg("r4",OWNER);reg("r5",7);reg("r7",0x24924925L);reg("r8",0);reg("r9",0);thread.overrideCounter(toAddr(0xc06fc));List<Object> cpu=new ArrayList<>();int total=0,steps=0;
   while(steps++<30000){monitor.checkCancelled();long p=thread.getCounter().getOffset();if(p==0xc0756)break;if(p==0xc32c8||p==0xa7104){ret();continue;}if(p==0x95018){int req=(int)reg("r1"),got=((req+quantum-1)/quantum)*quantum;cpu.add(obj("slice",reg("r8"),"request",req,"returned",got,"residue_before",reg("r9")));total+=got;reg("r0",got);ret();continue;}thread.stepInstruction();}
   if(steps>=30000)throw new IllegalStateException("frame limit");frames.add(obj("synthetic_cpu_quantum",quantum,"calls",cpu,"cycles_returned_sum",total,"master_residue_after",reg("r9"),"slices",reg("r8"),"instruction_steps",steps));
  }
  Path output=Path.of(getScriptArgs()[0]);Files.createDirectories(output.toAbsolutePath().getParent());
  Files.writeString(output,new GsonBuilder().setPrettyPrinting().create().toJson(obj("schema",1,"binary_sha256",sha,"checked_code_sha256",HASHES,"boundary","Original IRQ query C1058, acknowledge C13DC, line counter C3314. No renderer: descriptor null. CPU frame loop C06FC..C0754 original; only CPU return, scheduler and sound stubbed in frame-budget cases. No original 68000 execution or interrupt latency measured.","irq_queries",queryCases,"irq_acknowledgements",ackCases,"line_sequences",lines,"vertical_expiry",vertical,"frame_budgets",frames))+"\n");println("PASS IRQ32 queries32ack4countersequences2framebudgets");
 }
}

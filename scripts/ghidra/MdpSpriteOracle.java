// Execute original M2 sprite helpers and bounded geometry blocks on synthetic data.
// @category SpaceHarrier
// Usage: -postScript MdpSpriteOracle.java /absolute/output.json
// Import emulator/m2engage without analysis. This script never modifies the program.
import ghidra.app.plugin.processors.sleigh.SleighLanguage;
import ghidra.pcode.emu.PcodeEmulator;
import ghidra.pcode.emu.PcodeThread;
import ghidra.pcode.exec.PcodeExecutorStatePiece.Reason;
import ghidra.program.model.lang.Register;
import ghidra.util.task.TaskMonitor;
import ghidra.app.script.GhidraScript;
import ghidra.program.model.address.Address;
import ghidra.program.model.lang.RegisterValue;
import com.google.gson.GsonBuilder;
import java.math.BigInteger;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public class MdpSpriteOracle extends GhidraScript {
    private static final long CTX = 0x10000000L;
    private static final long RAM = 0x20000000L;
    private static final long STACK = 0x30001000L;
    private static final long SENTINEL = 0x40000000L;
    private static final long MASK32 = 0xffffffffL;
    private static final String BINARY_SHA256 =
        "2374ddca2241d2a040f587a1e86359c3d3d5f1dc93e566588b35e15bee73178f";

    private final class OracleMachine {
        private final PcodeEmulator machine;
        private final PcodeThread<byte[]> thread;
        OracleMachine(Address entry) throws Exception {
            machine = new PcodeEmulator((SleighLanguage) currentProgram.getLanguage());
            thread = machine.newThread();
            entry = toAddr(0xc1084);
            byte[] code = new byte[0x1800];
            currentProgram.getMemory().getBytes(entry, code);
            writeMemory(entry, code);
            byte[] lut=new byte[64];currentProgram.getMemory().getBytes(toAddr(0x23a9f0),lut);writeMemory(toAddr(0x23a9f0),lut);
        }
        private byte[] le(long value, int size) {
            byte[] bytes = new byte[size];
            for (int i = 0; i < size; i++) bytes[i] = (byte)(value >>> (8 * i));
            return bytes;
        }
        void writeMemory(Address address, byte[] bytes) {
            machine.getSharedState().setVar(address, bytes.length, true, bytes);
        }
        void writeMemoryValue(Address address, int size, long value) {
            writeMemory(address, le(value, size));
        }
        byte[] readMemory(Address address, int size) {
            return machine.getSharedState().getVar(address, size, true, Reason.INSPECT);
        }
        byte readMemoryByte(Address address) { return readMemory(address, 1)[0]; }
        void writeRegister(String name, long value) {
            writeRegister(currentProgram.getRegister(name), value);
        }
        void writeRegister(Register reg, long value) {
            if (reg.equals(getPCRegister())) thread.overrideCounter(toAddr(value));
            else thread.getState().setVar(reg, le(value, reg.getMinimumByteSize()));
        }
        BigInteger readRegister(String name) {
            byte[] raw = thread.getState().getVar(currentProgram.getRegister(name), Reason.INSPECT);
            long value = 0;
            for (int i = 0; i < raw.length; i++) value |= ((long)raw[i] & 255) << (8 * i);
            return BigInteger.valueOf(value & MASK32);
        }
        Register getPCRegister() { return currentProgram.getLanguage().getProgramCounter(); }
        Register getStackPointerRegister() { return currentProgram.getCompilerSpec().getStackPointer(); }
        void setContextRegister(RegisterValue context) { thread.overrideContext(context); }
        Address getExecutionAddress() { return thread.getCounter(); }
        boolean step(TaskMonitor monitor) throws Exception {
            monitor.checkCancelled();
            thread.stepInstruction();
            return true;
        }
        String getLastError() { return "p-code execution failure"; }
        void dispose() { }
    }

    private static Map<String, Object> obj(Object... pairs) {
        Map<String, Object> result = new LinkedHashMap<>();
        for (int i = 0; i < pairs.length; i += 2)
            result.put((String) pairs[i], pairs[i + 1]);
        return result;
    }

    private long u32(OracleMachine emu, long address) {
        byte[] b = emu.readMemory(toAddr(address), 4);
        return ((long)b[0] & 255) | (((long)b[1] & 255) << 8)
            | (((long)b[2] & 255) << 16) | (((long)b[3] & 255) << 24);
    }

    private long reg(OracleMachine emu, String name) {
        return emu.readRegister(name).longValue() & MASK32;
    }

    private void w32(OracleMachine emu, long address, long value) {
        emu.writeMemoryValue(toAddr(address), 4, value & MASK32);
    }


    void init(OracleMachine e,long entry) {
        e.writeMemory(toAddr(CTX),new byte[0x1000]);
        e.writeMemory(toAddr(RAM),new byte[0x20000]);
        e.writeMemory(toAddr(STACK-0x100),new byte[0x200]);
        for(int i=0;i<13;i++)e.writeRegister("r"+i,0);
        for(String f:new String[]{"CY","ZR","NG","OV","TB","ISAModeSwitch"})if(currentProgram.getRegister(f)!=null)e.writeRegister(f,0);
        e.writeRegister(e.getStackPointerRegister(),STACK);e.writeRegister("lr",SENTINEL|1);
        e.writeRegister(e.getPCRegister(),entry);
        RegisterValue ctx=new RegisterValue(currentProgram.getLanguage().getContextBaseRegister(),BigInteger.ZERO);
        ctx=ctx.combineValues(new RegisterValue(currentProgram.getRegister("TMode"),BigInteger.ONE));e.setContextRegister(ctx);
    }
    void word(OracleMachine e,long a,int v){e.writeMemoryValue(toAddr(a),2,v);}
    int until(OracleMachine e,long end)throws Exception {int n=0;while(e.getExecutionAddress().getOffset()!=end&&n++<10000)e.step(monitor);if(n>=10000)throw new IllegalStateException("limit "+e.getExecutionAddress());return n;}
    List<Integer> words(OracleMachine e,long a,int n){byte[]b=e.readMemory(toAddr(a),n*2);List<Integer>v=new ArrayList<>();for(int i=0;i<n;i++)v.add((b[2*i]&255)|((b[2*i+1]&255)<<8));return v;}
    Map<String,Object> shrink(String name,int xpos,int span,int attr)throws Exception {
      OracleMachine e=new OracleMachine(toAddr(0xc1084));init(e,0xc1084);
      w32(e,CTX,16);w32(e,CTX+12,CTX+0x100);e.writeMemory(toAddr(CTX+0x80),new byte[]{1,2,3,4,5,6,7,8});
      e.writeRegister("r0",CTX);e.writeRegister("r1",xpos);e.writeRegister("r2",CTX+0x80);e.writeRegister("r3",attr);w32(e,STACK,span);
      int n=until(e,SENTINEL);return obj("name",name,"kind","shrink","x",xpos,"span",span,"attr",attr,"pixels",words(e,CTX+0x100,16),"steps",n);
    }
    Map<String,Object> tile(String name,int attr,int size,int row)throws Exception {
      OracleMachine e=new OracleMachine(toAddr(0xc12d0));init(e,0xc12d0);
      // row nibble patterns distinguish VRAM banks and vertical/horizontal flips.
      for(int bank=0;bank<2;bank++)for(int y=0;y<8;y++){int a=(bank*0x10000)+32+y*4;word(e,RAM+a,bank==0?((y+1)<<12)|0x234:((y+8)<<12)|0xabc);word(e,RAM+a+2,bank==0?0x5678:0xdef1);}
      e.writeRegister("r0",RAM);e.writeRegister("r1",attr|1);e.writeRegister("r2",size);e.writeRegister("r3",row);w32(e,STACK,CTX);
      int n=until(e,SENTINEL);List<Integer>v=new ArrayList<>();for(byte b:e.readMemory(toAddr(CTX),8))v.add(b&255);
      return obj("name",name,"kind","tile","attr",attr|1,"size",size,"row",row,"pixels",v,"steps",n);
    }
    Map<String,Object> geometry(String name,int scan,int sy,int size,int xword,int zx,int zy,int attr)throws Exception {
      OracleMachine e=new OracleMachine(toAddr(0xc2664));init(e,0xc2664);
      final long sat=RAM,bank=RAM+0x11000;word(e,sat,sy);word(e,sat+2,size);word(e,sat+4,attr);word(e,sat+6,xword);word(e,bank+(xword>>>9)*16,zx);word(e,bank+(xword>>>9)*16+6,zy);
      w32(e,STACK+0x34,scan+128);e.writeRegister("r1",sat);e.writeRegister("r2",sy);e.writeRegister("r5",bank);
      int n=until(e,0xc2698);long delta=reg(e,"r2"),drawHeight=reg(e,"r1")>>3;
      Map<String,Object> out=obj("delta_mod1024",delta,"height",drawHeight,"accepted",delta<drawHeight);
      if(delta<drawHeight){
        e.writeRegister(e.getPCRegister(),0xc26f0);e.writeRegister("r0",RAM);e.writeRegister("r1",scan+128);e.writeRegister("r2",sat);e.writeRegister("r3",0);e.writeRegister("r5",bank);e.writeRegister("r8",4);
        // Previous Thumb IT state has expired at the microblock boundary.
        n+=until(e,0xc2720);out.put("source_y",reg(e,"r6"));n+=until(e,0xc275c);
        out.put("source_row",reg(e,"r6"));out.put("tile_attr",reg(e,"r4"));out.put("x_accum",reg(e,"r5"));out.put("x_step",u32(e,STACK+0x14));out.put("height_cells",u32(e,STACK+0x18));
      }
      return obj("name",name,"kind","geometry","input",obj("scan",scan,"sat_y",sy,"size",size,"xword",xword,"zx",zx,"zy",zy,"attr",attr),"output",out,"steps",n);
    }
    Map<String,Object> bank(int control)throws Exception {
      OracleMachine e=new OracleMachine(toAddr(0xc20a2));init(e,0xc20a2);
      e.writeMemoryValue(toAddr(CTX+0x38),1,control);w32(e,CTX+4,RAM);
      e.writeRegister("r10",CTX);e.writeRegister("r7",320);e.writeRegister("r6",0xe000);
      int n=until(e,(control&128)!=0?0xc2634:0xc20b0);
      return obj("name","control_"+control,"kind","bank","control",control,"enabled",(control&128)!=0,"base_bytes",(control&128)!=0?reg(e,"r2")-RAM:0,"steps",n);
    }
    public void run()throws Exception{
      if(!BINARY_SHA256.equalsIgnoreCase(currentProgram.getExecutableSHA256()))throw new IllegalStateException("wrong binary");
      List<Object> c=new ArrayList<>();for(int control:new int[]{0,0x11,0x80,0x91,0x9f,0xff})c.add(bank(control));for(int s=0;s<=8;s++)c.add(shrink("span_"+s,2,s,0));
      c.add(shrink("small_partial_left",-2,4,0));c.add(shrink("full_partial_left",-2,8,0));c.add(shrink("small_partial_right",14,4,0));c.add(shrink("priority",2,4,0x8000));
      for(int size:new int[]{0,0x1000,0x2000,0x4000,0x5000})for(int flip:new int[]{0,0x800,0x1000,0x1800})c.add(tile(String.format("tile_%04x_%04x",size,flip),0x6000|flip,size,2));
      c.add(geometry("unity",0,128,0x300,128,4096,4096,1));
      c.add(geometry("enlarge_vertical",33,128,0x300,128,4352,4352,1));
      c.add(geometry("zero_y",0,128,0x300,128,4096,0,1));
      c.add(geometry("tiny_y",0,128,0,128,4096,64,1));
      c.add(geometry("zero_x",0,128,0x300,128,0,4096,1));
      c.add(geometry("y_bit9",0,0x280,0x300,128,4096,4096,1));
      c.add(geometry("y_mod1024",0,0x480,0x300,128,4096,4096,1));
      c.add(geometry("negative_y_wrap",0,0xffff,0x300,128,4096,32767,1));
      c.add(geometry("fractional_vertical",7,128,0x300,128,2050,2050,0x1001));
      Files.writeString(Path.of(getScriptArgs()[0]),new GsonBuilder().setPrettyPrinting().create().toJson(obj("binary_sha256",BINARY_SHA256,"engine","Ghidra PcodeEmulator original ARM","scope","C1084/C12D0 complete helpers; geometry C2664..C2698 and C26F0..C275C; control C20A2..C20B0 or C2634; no whole-frame/timing claim","cases",c))+"\n");println("PASS "+c.size()+" sprite cases");
    }
}

// Execute original M2 plane/sprite composition, before palette conversion.
// @category SpaceHarrier
// Usage: -postScript MdpCompositeOracle.java /absolute/output.json
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

public class MdpCompositeOracle extends GhidraScript {
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

    Map<String,Object> one(boolean shadow,int plane,int sprite)throws Exception{
      OracleMachine e=new OracleMachine(toAddr(0xc2472));init(e,0xc2472);
      w32(e,CTX+0x60,1);e.writeMemoryValue(toAddr(CTX+0x20),1,shadow?8:0);w32(e,STACK+0x2c,CTX+0x200);
      word(e,STACK+0x2c4,plane);word(e,STACK+0x678,sprite);e.writeRegister("r10",CTX);e.writeRegister("r8",1);
      int n=until(e,0xc1e5c);int result=e.readMemoryByte(toAddr(CTX+0x200))&255;
      return obj("input",obj("shadow_enabled",shadow,"plane",plane,"sprite",sprite),"output_index",result,"steps",n);
    }
    public void run()throws Exception{
      if(!BINARY_SHA256.equalsIgnoreCase(currentProgram.getExecutableSHA256()))throw new IllegalStateException("wrong binary");
      List<Object>c=new ArrayList<>();int[]ps={0x22,0xa2,0x8022,0x80a2,0x62,0xe2,0x8062,0x80e2};
      int[]ss={0,0x13,0x3e,0x3f,0x53,0x7e,0x7f,0x8093,0x80be,0x80bf,0x80d3,0x80fe,0x80ff};
      for(boolean sh:new boolean[]{false,true})for(int plane:ps)for(int sprite:ss)c.add(one(sh,plane,sprite));
      Files.writeString(Path.of(getScriptArgs()[0]),new GsonBuilder().setPrettyPrinting().create().toJson(obj("binary_sha256",BINARY_SHA256,"engine","Ghidra PcodeEmulator original ARM","entry",0xc2472,"stop_before",0xc1e5c,"contract","One-pixel native composition, original register12 chooses shadow mode; no palette conversion or model rendering","cases",c))+"\n");println("PASS "+c.size()+" native composite cases");
    }
}

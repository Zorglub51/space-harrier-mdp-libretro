// Execute m2engage's original transformed-plane renderer on synthetic VRAM.
// @category SpaceHarrier
// Usage: -postScript MdpPlaneOracle.java /absolute/output.json
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

public class MdpPlaneOracle extends GhidraScript {
    private static final long RENDERER_FILE = 0x0b1bc0L;
    private static final long CODE_LENGTH = 0x264L;
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
            byte[] code = new byte[(int)CODE_LENGTH];
            currentProgram.getMemory().getBytes(entry, code);
            writeMemory(entry, code);
            byte[] lut = new byte[16];
            currentProgram.getMemory().getBytes(toAddr(0x23aa30), lut);
            writeMemory(toAddr(0x23aa30), lut);
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

    private void w32(OracleMachine emu, long address, long value) {
        emu.writeMemoryValue(toAddr(address), 4, value & MASK32);
    }


    private void word(OracleMachine e,long a,int v){e.writeMemoryValue(toAddr(a),2,v);}
    private void fixed(OracleMachine e,long a,int v){word(e,a,v>>>16);word(e,a+2,v);}
    private Map<String,Object> one(Address entry,String name,int ctl,int h,int v,int line,int xoff,int sx,int sy,int dx,int dy,int vx,int vy,int pri,int old) throws Exception {
        return one(entry,name,ctl,h,v,line,xoff,sx,sy,dx,dy,vx,vy,pri,old,0,0);
    }
    private Map<String,Object> one(Address entry,String name,int ctl,int h,int v,int line,int xoff,int sx,int sy,int dx,int dy,int vx,int vy,int pri,int old,int texture,int plane) throws Exception {
        OracleMachine e=new OracleMachine(entry);
        e.writeMemory(toAddr(CTX),new byte[0x200]);
        e.writeMemory(toAddr(STACK-0x200),new byte[0x400]);
        e.writeMemory(toAddr(RAM),new byte[0x20000]);
        final long desc=CTX+0x100, pixels=CTX+0x140;
        w32(e,CTX+4,RAM);e.writeMemoryValue(toAddr(CTX+0x34+plane),1,ctl);
        w32(e,desc,8);w32(e,desc+4,1);w32(e,desc+8,0);w32(e,desc+12,pixels);
        for(int i=0;i<8;i++)word(e,pixels+i*2,old);
        for(int t=1;t<=15;t++)for(int y=0;y<8;y++)for(int half=0;half<2;half++) {
            int packed=0;
            for(int p=0;p<4;p++) {
                int x=half*4+p;
                int colour=texture==0?t:1+((t-1+x+3*y)%15);
                if(texture==2 && (x+y)%3==0)colour=0;
                packed=(packed<<4)|colour;
            }
            word(e,RAM+t*32+y*4+half*2,packed);
        }
        int[] shifts={5,6,0,7};int cols=1<<shifts[h],rows=1<<shifts[v];
        for(int y=0;y<rows;y++)for(int x=0;x<cols;x++)word(e,RAM+0x8000+(y*cols+x)*2,pri | (1+(x+3*y)%15));
        for(int l=0;l<240;l++){
            long a=RAM+((ctl&31)<<12)+l*16;word(e,a,4096);word(e,a+2,0);fixed(e,a+8,0);fixed(e,a+12,((l+7)%32)*8*4096);
        }
        long a=RAM+((ctl&31)<<12)+((ctl&32)!=0?line*16:0);
        word(e,a,dx);word(e,a+2,dy);word(e,a+4,vx);word(e,a+6,vy);fixed(e,a+8,sx);fixed(e,a+12,sy);
        for(int r=0;r<13;r++)e.writeRegister("r"+r,0);
        for(String f:new String[]{"CY","ZR","NG","OV","TB","ISAModeSwitch"})if(currentProgram.getRegister(f)!=null)e.writeRegister(f,0);
        e.writeRegister("r0",CTX);e.writeRegister("r1",plane);e.writeRegister("r2",0x8000);e.writeRegister("r3",h);
        e.writeRegister(e.getStackPointerRegister(),STACK);e.writeRegister("lr",SENTINEL|1);e.writeRegister(e.getPCRegister(),entry.getOffset());
        w32(e,STACK,v);w32(e,STACK+4,xoff);w32(e,STACK+8,line);w32(e,STACK+12,desc);
        RegisterValue context=new RegisterValue(currentProgram.getLanguage().getContextBaseRegister(),BigInteger.ZERO);
        context=context.combineValues(new RegisterValue(currentProgram.getRegister("TMode"),BigInteger.ONE));e.setContextRegister(context);
        int steps=0;while(e.getExecutionAddress().getOffset()!=SENTINEL && steps++<10000)e.step(monitor);
        if(steps>=10000)throw new IllegalStateException("step limit "+name+" at "+e.getExecutionAddress());
        List<Integer> output=new ArrayList<>();byte[] bytes=e.readMemory(toAddr(pixels),16);for(int i=0;i<8;i++)output.add((bytes[i*2]&255)|((bytes[i*2+1]&255)<<8));
        return obj("name",name,"input",obj("control",ctl,"h",h,"v",v,"line",line,"xoff",xoff,"sx",sx,"sy",sy,"dx",dx,"dy",dy,"vx",vx,"vy",vy,"attr_flags",pri,"old",old,"texture",texture,"plane",plane),"pixels",output,"steps",steps);
    }
    @Override public void run() throws Exception {
        if(!BINARY_SHA256.equalsIgnoreCase(currentProgram.getExecutableSHA256()))throw new IllegalArgumentException("hash");
        if(getScriptArgs().length!=1)throw new IllegalArgumentException("usage: output.json");
        List<Address> entries=currentProgram.getMemory().locateAddressesForFileOffset(RENDERER_FILE);
        if(entries.size()!=1)throw new IllegalStateException("Ambiguous renderer mapping");
        Address entry=entries.get(0);
        byte[] entryBytes=new byte[4];currentProgram.getMemory().getBytes(entry,entryBytes);
        if(!Arrays.equals(entryBytes,new byte[]{0x2d,(byte)0xe9,(byte)0xf0,0x4f}))
            throw new IllegalArgumentException("Unexpected renderer entry");
        List<Object> cases=new ArrayList<>();
        for(int y:new int[]{0,223,224,335,336,431,432,511,512,-1})
            cases.add(one(entry,"wrap_y_"+y,0xf0,1,1,53,0,0,y*4096,4096,0,0,0,0,0));
        for(int y:new int[]{-1,512})cases.add(one(entry,"clamp_y_"+y,0xb0,1,1,53,0,-4096,y*4096,4096,0,0,0,0,0));
        cases.add(one(entry,"wrap_256_negative_x",0xf0,0,1,0,0,-4096,0,4096,0,0,0,0,0));
        cases.add(one(entry,"wrap_1024_x",0xf0,3,0,223,0,1023*4096,0,4096,0,0,0,0,0));
        cases.add(one(entry,"negative_dx_and_dy",0xf0,1,1,0,0,8*4096,8*4096,-4096,-4096,0,0,0,0));
        cases.add(one(entry,"line_y_step",0xf0,1,1,223,0,0,223*4096,4096,4096,0,0,0,0));
        cases.add(one(entry,"global_affine",0xd0,1,1,10,5,0,0,4096,0,0,4096,0,0));
        cases.add(one(entry,"high_priority",0xf0,1,1,53,0,0,0,4096,0,0,0,0xc000,0));
        cases.add(one(entry,"low_vs_high",0xf0,1,1,53,0,0,0,4096,0,0,0,0x4000,0x80ae));
        cases.add(one(entry,"line_xoff_is_not_added",0xf0,1,1,53,5,0,0,4096,0,0,0,0,0));
        cases.add(one(entry,"flip_x",0xf0,1,1,53,0,2*4096,3*4096,4096,0,0,0,0x0800,0,1,0));
        cases.add(one(entry,"flip_y",0xf0,1,1,53,0,2*4096,3*4096,4096,0,0,0,0x1000,0,1,0));
        cases.add(one(entry,"flip_xy",0xf0,1,1,53,0,2*4096,3*4096,4096,0,0,0,0x1800,0,1,0));
        cases.add(one(entry,"transparent_high",0xf0,1,1,53,0,0,0,4096,0,0,0,0x8000,4,2,0));
        cases.add(one(entry,"transparent_low",0xf0,1,1,53,0,0,0,4096,0,0,0,0x4000,0x3e,2,0));
        cases.add(one(entry,"encoding2_is_8pixels",0xf0,2,2,53,0,7*4096,7*4096,4096,4096,0,0,0,0,1,0));
        cases.add(one(entry,"plane_b_palette3",0xf0,1,1,53,0,2*4096,3*4096,4096,0,0,0,0x6000,0,1,1));
        cases.add(one(entry,"perline_ignores_affine_fields",0xf0,1,1,53,5,0,0,4096,0,4096,4096,0,0,1,0));
        cases.add(one(entry,"upper_table_bank31",0xff,1,1,223,0,0,224*4096,4096,0,0,0,0,0,1,0));
        cases.add(one(entry,"lower_table_bank4",0xe4,1,1,53,0,0,224*4096,4096,0,0,0,0,0,1,0));
        Map<String,Object> source=obj("binary_sha256",BINARY_SHA256,"renderer_file_offset",RENDERER_FILE,
            "renderer_loaded_address",entry.getOffset(),"engine","Ghidra PcodeEmulator ARM p-code",
            "ghidra_version",ghidra.framework.Application.getApplicationVersion(),
            "execution_boundary","Original C1BC0 function entry through its native return",
            "synthetic_vram_recipe",1,
            "pixel_encoding","colour in bits0..5, opaque plane priority in bit15, high-priority marker in bit7");
        Files.writeString(Path.of(getScriptArgs()[0]),new GsonBuilder().setPrettyPrinting().create().toJson(obj("schema",1,"source",source,"cases",cases))+"\n");
        println("PASS "+cases.size()+" native plane cases");
    }
}

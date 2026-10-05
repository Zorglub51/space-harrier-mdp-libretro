// Measure original M2 sprite traversal, selection and raster output using synthetic VRAM.
// @category SpaceHarrier
// Usage: -postScript MdpSpriteListOracle.java OUTPUT_JSON
// Stops at C2472 before plane/sprite composition. No game assets are included.
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
import java.security.MessageDigest;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public class MdpSpriteListOracle extends GhidraScript {
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
        OracleMachine() throws Exception {
            machine = new PcodeEmulator((SleighLanguage) currentProgram.getLanguage());
            thread = machine.newThread();
            Address entry = toAddr(0xc1000);
            byte[] code = new byte[0x2500];
            currentProgram.getMemory().getBytes(entry, code);
            writeMemory(entry, code);
            byte[] lut = new byte[0x200];
            currentProgram.getMemory().getBytes(toAddr(0x23a9f0), lut);
            writeMemory(toAddr(0x23a9f0), lut);
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

    private long reg(OracleMachine emu, String name) {
        return emu.readRegister(name).longValue() & MASK32;
    }

    private void w32(OracleMachine emu, long address, long value) {
        emu.writeMemoryValue(toAddr(address), 4, value & MASK32);
    }


    private void init(OracleMachine emu, long entry) {
        emu.writeMemory(toAddr(CTX), new byte[0x1000]);
        emu.writeMemory(toAddr(RAM), new byte[0x20000]);
        emu.writeMemory(toAddr(STACK - 0x100), new byte[0x200]);
        for (int index = 0; index < 13; index++) emu.writeRegister("r" + index, 0);
        for (String flag : new String[]{"CY", "ZR", "NG", "OV", "TB", "ISAModeSwitch"})
            if (currentProgram.getRegister(flag) != null) emu.writeRegister(flag, 0);
        emu.writeRegister(emu.getStackPointerRegister(), STACK);
        emu.writeRegister("lr", SENTINEL | 1);
        emu.writeRegister(emu.getPCRegister(), entry);
        emu.setContextRegister(thumbContext());
    }

    private static final int FRAME_WIDTH = 474;
    private static final int ACTIVE_HEIGHT = 224;
    private static final int MAX_INSTRUCTIONS = 500000;
    private static final long RENDER_ENTRY = 0xc1e24;
    private static final long COMPOSITE_ENTRY = 0xc2472;
    private static final long PALETTE_ENTRY = 0xc1e5c;
    private static final long MEMSET_ENTRY = 0x265e8;

    private String sha256(byte[] bytes) throws Exception {
        byte[] digest = MessageDigest.getInstance("SHA-256").digest(bytes);
        StringBuilder text = new StringBuilder();
        for (byte value : digest) text.append(String.format("%02x", value & 255));
        return text.toString();
    }

    private byte[] input(Path directory, String name, int expectedSize,
            Map<String, Object> hashes) throws Exception {
        byte[] data = Files.readAllBytes(directory.resolve(name));
        if (data.length != expectedSize)
            throw new IllegalArgumentException(name + ": expected " + expectedSize
                + " bytes, received " + data.length);
        hashes.put(name, sha256(data));
        return data;
    }

    private RegisterValue thumbContext() {
        RegisterValue context = new RegisterValue(
            currentProgram.getLanguage().getContextBaseRegister(), BigInteger.ZERO);
        return context.combineValues(new RegisterValue(
            currentProgram.getRegister("TMode"), BigInteger.ONE));
    }


    private static final class Case {
        final String name;
        int width = 320, scan = 0, reg5 = 0x70, reg12 = 0x81, reg36;
        final List<int[]> writes = new ArrayList<>();
        Case(String name, boolean zoom) { this.name = name; reg36 = zoom ? 0x91 : 0; }
        Case sat(int index, int y, int size, int attr, int x) {
            int base = ((reg5 & 0x7f) << 9) | (index << 3);
            writes.add(new int[]{base,y,size,attr,x}); return this;
        }
        Case zoom(int index, int x, int y) {
            int base = ((reg36 & 31) << 12) + index*16;
            writes.add(new int[]{base,x,0,0,y}); return this;
        }
    }
    private Case chain(String name, boolean zoom, int width, int count, int cells) {
        Case c = new Case(name, zoom); c.width = width; c.reg12 = width == 320 ? 0x81 : 0;
        for (int i=0;i<count;i++) c.sat(i,128,((cells-1)<<10)|(i+1<count?i+1:0),
            0x100+i*4|((i&3)<<13),128+(i*12)%300);
        return c;
    }
    private void write16(OracleMachine e, long address, int value) {
        e.writeMemoryValue(toAddr(address),2,value);
    }
    private List<Integer> words(OracleMachine e, long address, int count) {
        byte[] b=e.readMemory(toAddr(address), count*2); List<Integer> result=new ArrayList<>();
        for(int i=0;i<count;i++) result.add((b[i*2]&255)|((b[i*2+1]&255)<<8));
        return result;
    }
    private Map<String,Object> one(Case c) throws Exception {
        OracleMachine e=new OracleMachine(); init(e,RENDER_ENTRY);
        e.writeMemory(toAddr(STACK-0x4000),new byte[0x5000]);
        byte[] vram = new byte[0x20000];
        for(int tile=0;tile<4096;tile++) for(int row=0;row<8;row++) {
            for(int col=0;col<2;col++) {
                int value=0;
                for(int nibble=0;nibble<4;nibble++)
                    value=(value<<4)|(1+(tile+row*3+(col*4+nibble)*2+(tile>=2048?4:0))%15);
                int p=tile*32+row*4+col*2; vram[p]=(byte)value;vram[p+1]=(byte)(value>>>8);
            }
        }
        e.writeMemory(toAddr(RAM),vram);
        // A zero SAT prevents unspecified links from following pattern data.
        e.writeMemory(toAddr(RAM+((c.reg5&0x7f)<<9)),new byte[0x400]);
        if((c.reg36&128)!=0) for(int i=0;i<128;i++) {
            write16(e,RAM+((c.reg36&31)<<12)+i*16,4096);
            write16(e,RAM+((c.reg36&31)<<12)+i*16+6,4096);
        }
        for(int[] write:c.writes) for(int i=1;i<write.length;i++)
            write16(e,RAM+write[0]+2*(i-1),write[i]);
        w32(e,CTX,CTX+0x1000);w32(e,CTX+4,RAM);w32(e,CTX+8,CTX+0x1200);
        e.writeMemory(toAddr(CTX+0x1000),new byte[256]);
        e.writeMemory(toAddr(CTX+0x1200),new byte[128]);
        byte[] regs=new byte[64]; regs[1]=0x40;regs[5]=(byte)c.reg5;
        regs[12]=(byte)c.reg12;regs[36]=(byte)c.reg36;
        e.writeMemory(toAddr(CTX+0x14),regs);
        w32(e,CTX+0x60,474);w32(e,CTX+0x64,240);w32(e,CTX+0x68,c.width);w32(e,CTX+0x6c,224);
        w32(e,CTX+0x1300,CTX+0x2000);e.writeMemory(toAddr(CTX+0x2000),new byte[948]);
        e.writeRegister("r0",CTX);e.writeRegister("r1",c.scan);e.writeRegister("r2",CTX+0x1300);
        List<Integer> visited=new ArrayList<>(), selected=new ArrayList<>(), drawOrder=new ArrayList<>();
        List<Object> cells=new ArrayList<>();
        int current=-1, steps=0,memsets=0; long remaining=-1;
        while(steps++<MAX_INSTRUCTIONS) {
            long pc=e.getExecutionAddress().getOffset();
            if(pc==MEMSET_ENTRY) {
                long p=reg(e,"r0"),len=reg(e,"r2");
                if(p<STACK-0x4000||p+len>STACK+0x1000) throw new IllegalStateException("memset range");
                byte[] bytes=new byte[(int)len];Arrays.fill(bytes,(byte)reg(e,"r1"));
                e.writeMemory(toAddr(p),bytes);e.writeRegister(e.getPCRegister(),reg(e,"lr")&~1L);
                e.setContextRegister(thumbContext());memsets++;continue;
            }
            if(pc==0xc20e2) visited.add((int)reg(e,"r2"));
            if(pc==0xc264e) visited.add((int)reg(e,"r0"));
            if(pc==0xc211e) selected.add((int)reg(e,"r2"));
            if(pc==0xc26a2) selected.add((int)reg(e,"r0"));
            if(pc==0xc2134||pc==0xc26be) remaining=reg(e,"r11");
            if(pc==0xc2152||pc==0xc26dc) {
                current=e.readMemoryByte(toAddr(reg(e,"r2")))&255;drawOrder.add(current);
            }
            if(pc==0xc21cc) cells.add(obj("sprite",current,"attr",reg(e,"r2"),
                "x",(int)reg(e,"r3"),"path","plain"));
            if(pc==0xc12d0) cells.add(obj("sprite",current,"attr",reg(e,"r1"),
                "row",reg(e,"r3"),"path","zoom"));
            if(pc==COMPOSITE_ENTRY) {
                long sp=reg(e,e.getStackPointerRegister().getName());
                return obj("name",c.name,"input",obj("width",c.width,"scanline",c.scan,
                    "reg5",c.reg5,"reg12",c.reg12,"reg36",c.reg36,"vram_writes",c.writes),
                    "output",obj("visited",visited,"selected",selected,"draw_order",drawOrder,
                    "remaining_columns",remaining,"cells",cells,
                    "pixels",words(e,sp+0x678,c.width)),"steps",steps,"memset_calls",memsets);
            }
            if(pc<0xc1000||pc>=0xc3500) throw new IllegalStateException(c.name+" unexpected PC "+Long.toHexString(pc));
            e.step(monitor);
        }
        throw new IllegalStateException(c.name+" instruction limit");
    }
    public void run() throws Exception {
        if(!BINARY_SHA256.equalsIgnoreCase(currentProgram.getExecutableSHA256()))
            throw new IllegalStateException("Wrong binary SHA256");
        if(getScriptArgs().length!=1) throw new IllegalArgumentException("Expected OUTPUT_JSON");
        List<Case> cases=new ArrayList<>();
        for(boolean z:new boolean[]{false,true}) {
            String p=z?"zoom_":"plain_";
            for(int width:new int[]{256,320}) {
                cases.add(chain(p+"sprite_limit_"+width,z,width,24,1));
                cases.add(chain(p+"column_limit_"+width,z,width,16,4));
            }
            Case c=chain(p+"natural_end_39_columns",z,320,10,4);
            c.writes.get(9)[2]=2<<10;cases.add(c);
            c=chain(p+"natural_end_38_columns",z,320,10,4);
            c.writes.get(9)[2]=1<<10;cases.add(c);
            c=chain(p+"budget_cross_39_then_four",z,320,11,4);
            c.writes.get(0)[2]=(2<<10)|1;cases.add(c);
            c=new Case(p+"all_128_links_last_visible",z);
            for(int i=0;i<128;i++) c.sat(i,i==127?128:500,i==127?0:i+1,0x100,128);
            cases.add(c);
            c=new Case(p+"cycle_0_3_1_3",z);c.sat(0,128,3,0x100,128).sat(3,128,1,0x104,140).sat(1,128,3,0x108,152);cases.add(c);
            c=new Case(p+"first_x_zero",z);c.sat(0,128,1,0x100,0).sat(1,128,0,0x104,128);cases.add(c);
            c=new Case(p+"middle_x_zero",z);c.sat(0,128,1,0x100,128).sat(1,128,2,0x104,0).sat(2,128,0,0x108,160);cases.add(c);
            c=new Case(p+"off_line_x_zero",z);c.sat(0,500,1,0x100,0).sat(1,128,0,0x104,128);cases.add(c);
            c=new Case(p+"x_low9_zero_with_zoom_index",z);c.sat(0,128,1,0x100,0x600).sat(1,128,0,0x104,128);cases.add(c);
            c=chain(p+"offscreen_counted",z,320,24,1);for(int i=0;i<23;i++)c.writes.get(i)[4]=1;cases.add(c);
            c=new Case(p+"earliest_sat_wins",z);c.sat(0,128,1,0x100,128).sat(1,128,0,0x2104,128);cases.add(c);
            c=new Case(p+"odd_sat_or_alias",z);c.reg5=0x71;c.sat(0,128,64,0x100,128);c.writes.add(new int[]{0xe400,128,0,0x2104,160});cases.add(c);
            c=new Case(p+"sat_reg_bit7_ignored",z);c.reg5=0xf0;c.sat(0,128,0,0x100,128);cases.add(c);
            for(int interlace:new int[]{0,2,4,6}) {
                c=new Case(p+"reg12_interlace_"+interlace,z);c.reg12=0x81|interlace;
                c.scan=9;c.sat(0,128,1,0x100,128).sat(1,137,0,0x104,160);cases.add(c);
            }
            for(int flags:new int[]{0,0x1000,0x2000,0x4000,0x5000}) {
                c=new Case(p+"size_flags_"+Integer.toHexString(flags),z);
                c.sat(0,128,flags,0x2100,128);cases.add(c);
            }
            c=chain(p+"transparent_still_counted",z,320,24,1);
            for(int i=0;i<23;i++) {
                int tile=0x100+i*4;
                c.writes.add(new int[]{tile*32,0,0});
            }
            cases.add(c);
            c=new Case(p+"transparent_earlier_preserves_later",z);
            c.sat(0,128,1,0x100,128).sat(1,128,0,0xa104,128);
            c.writes.add(new int[]{0x100*32,0x0f00,0x00f0});cases.add(c);
            for(int attr:new int[]{0x7fe,0x7ff,0xffe,0xfff,0x17ff,0x1fff,0x7fff,0xffff}) {
                c=new Case(p+"tile_attr_carry_"+Integer.toHexString(attr),z);
                c.scan=8;c.sat(0,128,0x500,attr,144);cases.add(c);
            }
        }
        Case c=chain("zoom_reduction_does_not_reduce_budget",true,320,16,4);c.zoom(0,512,4096);cases.add(c);
        c=chain("zoom_zero_x_still_counted",true,320,24,1);c.zoom(0,0,4096);cases.add(c);
        c=chain("zoom_zero_y_not_counted",true,320,24,1);c.zoom(0,4096,0);cases.add(c);
        c=chain("zoom_fractional_height_selection",true,320,4,1);c.scan=1;c.zoom(0,4096,512);cases.add(c);
        List<Object> output=new ArrayList<>();
        for(Case item:cases) {output.add(one(item));println("PASS "+item.name);}
        Map<String,Object> fixture=obj("binary_sha256",BINARY_SHA256,
            "engine","Ghidra PcodeEmulator original ARM", "entry",RENDER_ENTRY,"stop_before",COMPOSITE_ENTRY,
            "scope","Original C1E24 sprite selection and raster output; synthetic VRAM; before composition and NEON palette conversion; external memset only is replaced",
            "vram_initialization",obj("size_bytes",131072,
                "pattern","For physical tile 0..4095, row 0..7, pixel 0..7: nibble = 1+(tile+row*3+pixel*2+(tile>=2048?4:0))%15. Pack pixels 0..3 then 4..7 most-significant nibble first into two words.",
                "order","Pattern fill; clear 1024 bytes at (reg5&127)<<9; if reg36 bit7, set X/Y zoom factors 4096 for all128 entries; apply vram_writes sequentially",
                "vram_writes","Each array is [byte_address,word0,word1,...]; numeric words, little endian in ARM memory"),
            "cases",output);
        Files.writeString(Path.of(getScriptArgs()[0]),new GsonBuilder().setPrettyPrinting().create().toJson(fixture)+"\n");
        println("PASS "+output.size()+" original sprite-list cases");
    }
}

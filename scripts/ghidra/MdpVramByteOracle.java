// Execute original MDP direct-VRAM byte writes in both 64KiB banks, followed by word readback.
// @category SpaceHarrier
// Usage: -postScript MdpVramByteOracle.java /absolute/output.json
// Fixtures contain only synthetic inputs and hashes, never game assets.
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
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public class MdpVramByteOracle extends GhidraScript {
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
            Address entry = toAddr(ENTRY);
            byte[] code = new byte[(int)(CODE_END - ENTRY)];
            currentProgram.getMemory().getBytes(entry, code);
            if (!HANDLER_SHA256.equals(sha256(code)))
                throw new IllegalStateException("Loaded handler bytes differ from the private original");
            writeMemory(entry, code);
            byte[] byte_readCode=new byte[(int)(BYTE_READ_END-BYTE_READ_ENTRY)];
            currentProgram.getMemory().getBytes(toAddr(BYTE_READ_ENTRY),byte_readCode);
            if(!BYTE_READ_SHA256.equals(sha256(byte_readCode)))throw new IllegalStateException("BYTE_READ callback mismatch");
            writeMemory(toAddr(BYTE_READ_ENTRY),byte_readCode);

            byte[] readCode=new byte[(int)(READ_END-READ_ENTRY)];
            currentProgram.getMemory().getBytes(toAddr(READ_ENTRY),readCode);
            if(!READ_SHA256.equals(sha256(readCode)))throw new IllegalStateException("READ callback mismatch");
            writeMemory(toAddr(READ_ENTRY),readCode);

            byte[] byteWriteCode=new byte[(int)(BYTE_WRITE_END-BYTE_WRITE_ENTRY)];
            currentProgram.getMemory().getBytes(toAddr(BYTE_WRITE_ENTRY),byteWriteCode);
            if(!BYTE_WRITE_SHA256.equals(sha256(byteWriteCode)))throw new IllegalStateException("Byte-write callback mismatch");
            writeMemory(toAddr(BYTE_WRITE_ENTRY),byteWriteCode);

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

    private static final String HANDLER_SHA256 = "d07969110e42a6830564247764dfe5d780dc9205cf52036ceb18a5147bc2a55d";
    private static final long BYTE_WRITE_ENTRY=0xc09e4L, BYTE_WRITE_END=0xc0b1cL;
    private static final String BYTE_WRITE_SHA256="a2a378478a4415081a1a0fddcac7447df0b24f476dd95fd10440bcf46802e7c4";
    private static final long READ_ENTRY=0xc2af8L, READ_END=0xc2ca8L;
    private static final String READ_SHA256="32c1a29acc24568bd45c506434add51fa6b6b86fc4353b216253f3c37344c8d4";
    private static final long BYTE_READ_ENTRY=0xc090cL, BYTE_READ_END=0xc09e4L;
    private static final String BYTE_READ_SHA256="05fe937ca2d86e5412191694659b522b3fd3a6a5c715a606d86bc488d4d15e7e";
    private static final long ENTRY = 0xc2ca8L, CODE_END = 0xc32c8L;
    private static final long CRAM = RAM + 0x30000, VSRAM = RAM + 0x31000;
    private static final long READ_CALLBACK = 0x50000000L, OWNER = CTX + 0x800;
    private static final long DIAGNOSTIC = 0x9e818L;
    private static final int MAX_INSTRUCTIONS = 2500000;

    private RegisterValue thumbContext() {
        return new RegisterValue(currentProgram.getLanguage().getContextBaseRegister(), BigInteger.ZERO)
            .combineValues(new RegisterValue(currentProgram.getRegister("TMode"), BigInteger.ONE));
    }
    private static byte[] le(long value, int size) {
        byte[] b = new byte[size];
        for (int i = 0; i < size; i++) b[i] = (byte)(value >>> (8 * i));
        return b;
    }
    private String hex(byte[] bytes) {
        StringBuilder out = new StringBuilder();
        for (byte b : bytes) out.append(String.format("%02x", b & 255));
        return out.toString();
    }
    private String sha256(byte[] bytes) throws Exception {
        return hex(MessageDigest.getInstance("SHA-256").digest(bytes));
    }
    private long read(OracleMachine e, long address, int size) {
        byte[] b = e.readMemory(toAddr(address), size); long value = 0;
        for (int i = 0; i < size; i++) value |= ((long)b[i] & 255) << (8*i);
        return value;
    }
    private List<Integer> unsigned(byte[] bytes) {
        List<Integer> out = new ArrayList<>();
        for (byte b : bytes) out.add(b & 255);
        return out;
    }
    private byte[] seed(int size, int addend) {
        byte[] b = new byte[size];
        for (int i = 0; i < size; i++) b[i] = (byte)(i * 37 + (i >>> 16) * 29 + addend);
        return b;
    }
    private Map<String,Object> bank(OracleMachine e, long address, byte[] initial) throws Exception {
        byte[] after = e.readMemory(toAddr(address), initial.length);
        int changed = 0; List<Object> examples = new ArrayList<>();
        for (int i = 0; i < after.length; i++) if (after[i] != initial[i]) {
            changed++;
            if (examples.size() < 8) examples.add(obj("offset", i, "before", initial[i]&255, "after", after[i]&255));
        }
        return obj("sha256", sha256(after), "changed_bytes", changed, "first_changes", examples);
    }
    private Map<String,Object> state(OracleMachine e) {
        return obj("registers", unsigned(e.readMemory(toAddr(CTX+0x14),64)),
            "flags", read(e,CTX+0x58,4), "command_pending", (read(e,CTX+0x58,4)&8)!=0,
            "address", read(e,CTX+0x5c,2), "code", read(e,CTX+0x5e,1));
    }
    private Map<String,Object> call(OracleMachine e, long address, long data, boolean byteWrite, boolean reading) throws Exception {
        e.writeRegister("r0",byteWrite?CTX+0x900:CTX); e.writeRegister("r1",address); e.writeRegister("r2",data);
        e.writeRegister("lr",SENTINEL|1); e.writeRegister(e.getPCRegister(),reading?(byteWrite?BYTE_READ_ENTRY:READ_ENTRY):(byteWrite?BYTE_WRITE_ENTRY:ENTRY));
        e.setContextRegister(thumbContext());
        MessageDigest trace = MessageDigest.getInstance("SHA-256");
        List<Object> first = new ArrayList<>(); Object last = null; int count = 0, instructions = 0;
        String boundary = "return";
        while (e.getExecutionAddress().getOffset() != SENTINEL) {
            long pc = e.getExecutionAddress().getOffset();
            if (pc == DIAGNOSTIC || pc == 0x9eb38L) { boundary = pc == DIAGNOSTIC ? "diagnostic" : "diagnostic_log"; break; }
            if (pc == READ_CALLBACK) {
                if (reg(e,"r0") != 0x12345678L) throw new IllegalStateException("bus opaque owner mismatch");
                long source = reg(e,"r1");
                long value = 0xbeef0000L | ((source ^ (source>>>16) ^ 0xa55a) & 65535);
                trace.update(le(source,4)); trace.update(le(value,4));
                last = obj("address",source,"value",value);
                if (first.size()<8) first.add(last);
                count++;
                e.writeRegister("r0",value);
                e.writeRegister(e.getPCRegister(),reg(e,"lr")&~1L);
                e.setContextRegister(thumbContext());
                continue;
            }
            if (!((pc>=ENTRY && pc<CODE_END)||(pc>=BYTE_WRITE_ENTRY && pc<BYTE_WRITE_END)||(pc>=READ_ENTRY && pc<READ_END)||(pc>=BYTE_READ_ENTRY && pc<BYTE_READ_END))) throw new IllegalStateException("unexpected PC "+Long.toHexString(pc));
            if (++instructions>MAX_INSTRUCTIONS) throw new IllegalStateException("instruction limit");
            e.step(monitor);
        }
        if (boundary.equals("return") && reg(e,e.getStackPointerRegister().getName())!=STACK)
            throw new IllegalStateException("stack mismatch");
        Map<String,Object> out=obj("boundary",boundary,"native_instruction_steps",instructions,
            "bus_reads",obj("count",count,"first",first,"last",last,"sha256",hex(trace.digest())));
        if (reading && boundary.equals("return")) { out.put("read_result_u32",reg(e,"r0"));out.put("read_value",reg(e,"r0") & (byteWrite?255:65535)); }
        if (!boundary.equals("return")) out.put("diagnostic",obj("entry",e.getExecutionAddress().getOffset(),"caller_return",reg(e,"lr"),"argument_r2",reg(e,"r2")));
        return out;
    }
    private static final class Case {
        String name, kind; byte[] regs = new byte[64];
        long flags=0xa5000003L, profile=0; int address=0x2468, code=5, scanline=166;
        List<long[]> writes=new ArrayList<>();
        Case(String name,String kind){this.name=name;this.kind=kind;regs[1]=0x10;regs[15]=2;}
        Case write(long port,long data){writes.add(new long[]{port,data});return this;}
        Case write8(long port,long data){writes.add(new long[]{port,data,8});return this;}
        Case read(long port){writes.add(new long[]{port,0,0});return this;}
        Case read8(long port){writes.add(new long[]{port,0,1});return this;}
        Case command(int address,int code){return write(0xc00004,(address&0x3fff)|((code&3)<<14))
            .write(0xc00006,((address>>>14)&3)|((code&0x3c)<<2));}
    }
    private Map<String,Object> one(Case c) throws Exception {
        OracleMachine e=new OracleMachine(); init(e,ENTRY);
        byte[] vram=seed(131072,13),cram=seed(256,71),vsram=seed(128,149);
        e.writeMemory(toAddr(RAM),vram);e.writeMemory(toAddr(CRAM),cram);e.writeMemory(toAddr(VSRAM),vsram);
        w32(e,CTX+0x78,c.scanline);
        w32(e,CTX,CRAM);w32(e,CTX+4,RAM);w32(e,CTX+8,VSRAM);w32(e,CTX+0x10,OWNER);
        w32(e,CTX+0x920,CTX);w32(e,OWNER+8,READ_CALLBACK|1);w32(e,OWNER+0x1c,0x12345678);
        e.writeMemory(toAddr(CTX+0x14),c.regs);w32(e,CTX+0x54,c.profile);w32(e,CTX+0x58,c.flags);
        e.writeMemoryValue(toAddr(CTX+0x5c),2,c.address);e.writeMemoryValue(toAddr(CTX+0x5e),1,c.code);
        List<Object> writes=new ArrayList<>(),steps=new ArrayList<>();
        for(long[] w:c.writes)writes.add(operation(w));
        for(long[] w:c.writes){
            boolean reading=w.length==3&&w[2]<2;
            boolean byteAccess=w.length==3&&(w[2]==1||w[2]==8);
            Map<String,Object> step=call(e,w[0],w[1],byteAccess,reading);
            step.put("operation",operation(w));step.put("state",state(e));
            step.put("memory",obj("vram",bank(e,RAM,vram),"cram",bank(e,CRAM,cram),"vsram",bank(e,VSRAM,vsram)));
            step.put("cram_words",words(e,CRAM,128));step.put("vsram_native_words",words(e,VSRAM,64));
            steps.add(step);if(!step.get("boundary").equals("return"))break;
        }
        return obj("name",c.name,"kind",c.kind,"input",obj("registers",unsigned(c.regs),"flags",c.flags,
            "address",c.address,"code",c.code,"profile_tag",c.profile,"scanline",c.scanline,"operations",writes),"steps",steps);
    }
    private Map<String,Object> operation(long[] w){
        boolean reading=w.length==3&&w[2]<2;
        boolean byteAccess=w.length==3&&(w[2]==1||w[2]==8);
        Map<String,Object> out=obj("kind",reading?"read":"write","address",w[0],"width",byteAccess?8:16);
        if(!reading)out.put("data",w[1]);return out;
    }
    private List<Integer> words(OracleMachine e,long address,int count){
        List<Integer> out=new ArrayList<>();for(int i=0;i<count;i++)out.add((int)read(e,address+i*2,2));return out;
    }
    @Override public void run()throws Exception{
        if(getScriptArgs().length!=1)throw new IllegalArgumentException("Expected output JSON path");
        if(!BINARY_SHA256.equalsIgnoreCase(currentProgram.getExecutableSHA256()))throw new IllegalStateException("ELF SHA mismatch");
        List<Case> inputs=new ArrayList<>();
        for(long port:new long[]{0xd00000,0xd00001,0xd10000,0xd10001})
            inputs.add(new Case("vram_byte_"+Long.toHexString(port),"vram_byte").write8(port,0xab).read(port&~1L));
        List<Object> cases=new ArrayList<>();
        Map<String,Object> fixture=obj("schema_version",1,"binary_sha256",BINARY_SHA256,
            "handlers",obj("write",obj("entry",ENTRY,"sha256",HANDLER_SHA256),"read",obj("entry",READ_ENTRY,"sha256",READ_SHA256),
                "write8",obj("entry",BYTE_WRITE_ENTRY,"sha256",BYTE_WRITE_SHA256),"read8",obj("entry",BYTE_READ_ENTRY,"sha256",BYTE_READ_SHA256)),
            "execution_boundary","Original CPU byte-write callback and MDP write/read handlers through native return. No callback is intercepted in these four cases. No renderer or scheduler executed.",
            "memory_encoding","Numeric little-endian; VSRAM is native shifted backing. Video buffers initialized independently and never alias.",
            "memory_seed",obj("formula","byte[i]=(i*37+(i>>16)*29+addend)&255","vram",obj("size",131072,"addend",13),"cram",obj("size",256,"addend",71),"vsram",obj("size",128,"addend",149)),
            "bus_read_callback","0xbeef0000 | ((address ^ (address >> 16) ^ 0xa55a) & 0xffff)","cases",cases);
        for(Case c:inputs){cases.add(one(c));println("PASS "+c.name);}
        Path output=Path.of(getScriptArgs()[0]);Files.createDirectories(output.toAbsolutePath().getParent());
        Files.writeString(output,new GsonBuilder().setPrettyPrinting().serializeNulls().create().toJson(fixture)+"\n");
        println("PASS "+cases.size()+" original native video-port sequences");
    }
}

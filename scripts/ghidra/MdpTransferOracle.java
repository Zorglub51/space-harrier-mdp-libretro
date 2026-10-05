// Execute original m2engage MDP port writes on synthetic transfer sequences.
// @category SpaceHarrier
// Usage: -postScript MdpTransferOracle.java /absolute/output.json
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

public class MdpTransferOracle extends GhidraScript {
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
        for (int i = 0; i < size; i++) b[i] = (byte)(i * 37 + addend);
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
    private Map<String,Object> call(OracleMachine e, long address, long data, boolean byteWrite) throws Exception {
        e.writeRegister("r0",byteWrite?CTX+0x900:CTX); e.writeRegister("r1",address); e.writeRegister("r2",data);
        e.writeRegister("lr",SENTINEL|1); e.writeRegister(e.getPCRegister(),byteWrite?BYTE_WRITE_ENTRY:ENTRY);
        e.setContextRegister(thumbContext());
        MessageDigest trace = MessageDigest.getInstance("SHA-256");
        List<Object> first = new ArrayList<>(); Object last = null; int count = 0, instructions = 0;
        String boundary = "return";
        while (e.getExecutionAddress().getOffset() != SENTINEL) {
            long pc = e.getExecutionAddress().getOffset();
            if (pc == DIAGNOSTIC) { boundary = "diagnostic"; break; }
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
            if (!((pc>=ENTRY && pc<CODE_END)||(pc>=BYTE_WRITE_ENTRY && pc<BYTE_WRITE_END))) throw new IllegalStateException("unexpected PC "+Long.toHexString(pc));
            if (++instructions>MAX_INSTRUCTIONS) throw new IllegalStateException("instruction limit");
            e.step(monitor);
        }
        if (boundary.equals("return") && reg(e,e.getStackPointerRegister().getName())!=STACK)
            throw new IllegalStateException("stack mismatch");
        Map<String,Object> out=obj("boundary",boundary,"native_instruction_steps",instructions,
            "bus_reads",obj("count",count,"first",first,"last",last,"sha256",hex(trace.digest())));
        if (boundary.equals("diagnostic")) out.put("diagnostic",obj("entry",DIAGNOSTIC,"caller_return",reg(e,"lr"),"argument_r2",reg(e,"r2")));
        return out;
    }
    private static final class Case {
        String name, kind; byte[] regs = new byte[64];
        long flags=0xa5000003L, profile=0; int address=0x2468, code=5;
        List<long[]> writes=new ArrayList<>();
        Case(String name,String kind){this.name=name;this.kind=kind;regs[1]=0x10;regs[15]=2;}
        Case write(long port,long data){writes.add(new long[]{port,data});return this;}
        Case write8(long port,long data){writes.add(new long[]{port,data,8});return this;}
        Case command(int address,int code){return write(0xc00004,(address&0x3fff)|((code&3)<<14))
            .write(0xc00006,((address>>>14)&3)|((code&0x3c)<<2));}
    }
    private Case transfer(String name,String kind,int length,int dest,int inc,int source,int target,int data) {
        Case c = new Case(name,kind); c.regs[15]=(byte)inc;
        c.regs[19]=(byte)length; c.regs[20]=(byte)(length>>>8);
        if (kind.equals("dma68k")) {
            c.regs[21]=(byte)(source>>>1);c.regs[22]=(byte)(source>>>9);c.regs[23]=(byte)(source>>>17);
            c.command(dest,target);
        } else {
            c.regs[21]=(byte)source;c.regs[22]=(byte)(source>>>8);c.regs[23]=(byte)(kind.equals("fill")?0x80:0xc0);
            c.command(dest,kind.equals("fill")?0x21:0x30);
            if(kind.equals("fill")) c.write(0xc00000,data);
        }
        return c;
    }
    private Map<String,Object> one(Case c) throws Exception {
        OracleMachine e=new OracleMachine(); init(e,ENTRY);
        byte[] vram=seed(131072,13),cram=seed(256,71),vsram=seed(128,149);
        e.writeMemory(toAddr(RAM),vram);e.writeMemory(toAddr(CRAM),cram);e.writeMemory(toAddr(VSRAM),vsram);
        w32(e,CTX,CRAM);w32(e,CTX+4,RAM);w32(e,CTX+8,VSRAM);w32(e,CTX+0x10,OWNER);
        w32(e,CTX+0x920,CTX);w32(e,OWNER+8,READ_CALLBACK|1);w32(e,OWNER+0x1c,0x12345678);
        e.writeMemory(toAddr(CTX+0x14),c.regs);w32(e,CTX+0x54,c.profile);w32(e,CTX+0x58,c.flags);
        e.writeMemoryValue(toAddr(CTX+0x5c),2,c.address);e.writeMemoryValue(toAddr(CTX+0x5e),1,c.code);
        List<Object> writes=new ArrayList<>(),steps=new ArrayList<>();
        for(long[] w:c.writes){Map<String,Object> write=obj("address",w[0],"data",w[1]);if(w.length==3)write.put("width",8);writes.add(write);}
        for(long[] w:c.writes){
            Map<String,Object> step=call(e,w[0],w[1],w.length==3);
            Map<String,Object> write=obj("address",w[0],"data",w[1]);if(w.length==3)write.put("width",8);step.put("write",write);step.put("state",state(e));
            step.put("memory",obj("vram",bank(e,RAM,vram),"cram",bank(e,CRAM,cram),"vsram",bank(e,VSRAM,vsram)));
            steps.add(step);if(step.get("boundary").equals("diagnostic"))break;
        }
        return obj("name",c.name,"kind",c.kind,"input",obj("registers",unsigned(c.regs),"flags",c.flags,
            "address",c.address,"code",c.code,"profile_tag",c.profile,"writes",writes),"steps",steps);
    }
    @Override public void run() throws Exception {
        if(getScriptArgs().length!=1)throw new IllegalArgumentException("Expected output JSON path");
        if(!BINARY_SHA256.equalsIgnoreCase(currentProgram.getExecutableSHA256()))throw new IllegalStateException("Private reference ELF SHA256 mismatch");
        if(!currentProgram.getLanguageID().toString().startsWith("ARM:LE:32"))throw new IllegalStateException("Expected ARM little endian language");
        List<Case> inputs=new ArrayList<>();
        for(int n:new int[]{0,1,2,3,4,7,8,31,8191,65535})inputs.add(transfer("fill_length_"+n,"fill",n,0x100,2,0x1234,0,0x1234));
        inputs.add(transfer("fill_real_game_clear_zero_length","fill",0,0,1,0,0,0));
        for(int inc:new int[]{0,1,2,255})for(int dest:new int[]{0x100,0x101,0xfffe,0xffff})
            inputs.add(transfer("fill_inc_"+inc+"_dest_"+dest,"fill",4,dest,inc,0x1234,0,0x1234));
        for(int data:new int[]{0,0xffff,0xab00,0x00cd})inputs.add(transfer("fill_data_"+data,"fill",2,0x103,1,0x1234,0,data));
        for(int pending:new int[]{0,8}){
            Case c=transfer("fill_primed_pending_"+pending,"fill",4,0x100,2,0x1234,0,0x1234);
            c.writes.clear();c.code=0x21;c.address=0x100;c.flags|=pending;c.write(0xc00000,0x1234);inputs.add(c);
        }
        for(int invalidCode:new int[]{0x23,0x25}) {
            Case c=transfer("fill_invalid_code_"+invalidCode,"fill_diagnostic",4,0x100,2,0,0,0x1234);
            c.regs[23]=(byte)0x80;c.writes.clear();c.code=invalidCode;c.address=0x100;c.flags|=8;c.write(0xc00000,0x1234);inputs.add(c);
        }
        Case disabled=transfer("fill_dma_enable_clear","fill",4,0x100,2,0,0,0x1234);
        disabled.regs[1]=0;inputs.add(disabled);
        Case regBetween=transfer("fill_register_write_between_command_data","control",4,0x100,2,0,0,0x1234);
        regBetween.regs[23]=(byte)0x80;regBetween.writes.clear();
        regBetween.command(0x100,0x21).write(0xc00004,0x8f01).write(0xc00000,0x1234);inputs.add(regBetween);
        inputs.add(transfer("fill_second_data_diagnostic","fill",2,0x100,2,0,0,0x1234).write(0xc00002,0xabcd));
        inputs.add(transfer("fill_then_new_vram_command","fill",2,0x100,2,0,0,0x1234).command(0x500,1).write(0xc00002,0xabcd));
        for(int target:new int[]{0x21,0x23,0x25}){
            for(int n:new int[]{0,1,7})inputs.add(transfer("dma_target_"+target+"_length_"+n,"dma68k",n,0x7c,2,0x234560,target,0));
            for(int inc:new int[]{0,1,2,255})inputs.add(transfer("dma_target_"+target+"_single_inc_"+inc,"dma68k",1,0xfffe,inc,0xfffffe,target,0));
            inputs.add(transfer("dma_target_"+target+"_wrap","dma68k",4,0xfffe,2,0xfffffc,target,0));
            inputs.add(transfer("dma_target_"+target+"_odd_diagnostic","dma68k",2,0x101,2,0x234560,target,0));
            inputs.add(transfer("dma_target_"+target+"_becomes_odd_diagnostic","dma68k",3,0x100,1,0x234560,target,0));
        }
        for(int n:new int[]{0x7fff,0x8000,0x8001,0xffff})inputs.add(transfer("dma_large_"+n,"dma68k",n,0x4000,2,0xff8000,0x21,0));
        for(int enabled:new int[]{0,0x10}){
            Case c=transfer("dma_enable_"+enabled,"dma68k",4,0x100,2,0x234560,0x21,0);c.regs[1]=(byte)enabled;inputs.add(c);
        }
        for(int n:new int[]{0,1,4,0xffff})inputs.add(transfer("copy_length_"+n,"copy",n,0x100,2,0x200,0,0));
        for(int inc:new int[]{0,1,2,255})for(int delta:new int[]{-1,0,1})
            inputs.add(transfer("copy_overlap_inc_"+inc+"_delta_"+delta,"copy",7,0x200+delta,inc,0x200,0,0));
        inputs.add(transfer("copy_source_dest_wrap","copy",4,0xfffe,1,0xffff,0,0));
        inputs.add(transfer("copy_second_data_diagnostic","copy",4,0x100,2,0x200,0,0).write(0xc00000,0x1234));
        inputs.add(new Case("register_preserves_address_code","control").write(0xc00004,0x8f07));
        inputs.add(new Case("register_ignores_mode4_guard","control").write(0xc00004,0x9f55));
        inputs.add(new Case("pending_register_word_is_command_second","control").write(0xc00004,0x4321).write(0xc00004,0x8f03));
        inputs.add(new Case("data_clears_partial_command","control").write(0xc00004,0x4200).write(0xc00000,0x1234));
        inputs.add(new Case("data_odd_diagnostic","control").command(0x101,1).write(0xc00000,0x1234));
        for(int code:new int[]{0x21,0x31}) {
            Case c=transfer("copy_dispatch_code_"+code,"copy",4,0x100,2,0x200,0,0);
            c.kind="dispatch";c.writes.clear();c.command(0x100,code);inputs.add(c);
        }
        Case cpuInvalid=transfer("dma_dispatch_code_48","dma68k",4,0x100,2,0x234560,0x30,0);
        cpuInvalid.kind="dispatch";inputs.add(cpuInvalid);
        Case copy80=transfer("copy_dispatch_type_80","copy",4,0x100,2,0x200,0,0);
        copy80.kind="dispatch";copy80.regs[23]=(byte)0x80;inputs.add(copy80);
        Case fill23=transfer("fill_control_code_23_diagnostic","fill",4,0x100,2,0,0,0x1234);
        fill23.kind="dispatch";fill23.writes.clear();fill23.command(0x100,0x23);inputs.add(fill23);
        inputs.add(new Case("vsram_regular_mirrors","vsram_write").command(0,5).write(0xc00000,0x1234).write(0xc00002,0xabcd));
        inputs.add(new Case("vsram_high_overrides_only_mirrors","vsram_write").command(0,5).write(0xc00000,0x1234).write(0xc00002,0xabcd)
            .command(0x7c,5).write(0xc00000,0x5678).write(0xc00002,0x9abc));
        inputs.add(new Case("vsram_direct_mirrors","vsram_write").write(0xc00200,0x1234).write(0xc00202,0xabcd)
            .write(0xc0027c,0x5678).write(0xc0027e,0x9abc));
        for(long profile:new long[]{0,0x4f967b9eL,0xca196d58L}){
            Case c=transfer("data_code21_typeC0_profile_"+Long.toHexString(profile),"copy",4,0x100,2,0x200,0,0);
            c.kind="data_guard";c.writes.clear();c.code=0x21;c.address=0x100;c.profile=profile;c.write(0xc00000,0xabcd);inputs.add(c);
        }
        inputs.add(new Case("vsram_direct_write8_even","vsram_write8").write8(0xc00200,0xab));
        inputs.add(new Case("vsram_direct_write8_odd","vsram_write8").write8(0xc00203,0xcd));
        List<Object> cases=new ArrayList<>();
        Path output=Path.of(getScriptArgs()[0]);Files.createDirectories(output.toAbsolutePath().getParent());
        Map<String,Object> fixture=obj("schema_version",1,"binary_sha256",BINARY_SHA256,"handler_sha256",HANDLER_SHA256,
            "byte_write_callback",obj("loaded_va",BYTE_WRITE_ENTRY,"file_offset",BYTE_WRITE_ENTRY-0x10000,"sha256",BYTE_WRITE_SHA256),
            "entry",obj("loaded_va",ENTRY,"file_offset",ENTRY-0x10000,"code_end_exclusive",CODE_END),
            "execution_boundary","Original ARM/Thumb instructions from C2CA8 to return; synthetic read16 callback only. Diagnostic cases stop on entry to 9E818 without assuming return. No whole-machine timing claim.",
            "memory_encoding","Numeric little-endian storage. VSRAM uses M2's shifted backing, not MAME's logical layout.",
            "memory_seed",obj("formula","byte[i] = (i * multiplier + addend) & 255",
                "vram",obj("size",131072,"multiplier",37,"addend",13),
                "cram",obj("size",256,"multiplier",37,"addend",71),
                "vsram",obj("size",128,"multiplier",37,"addend",149)),
            "bus_read_callback",obj("value_formula","0xbeef0000 | ((address ^ (address >> 16) ^ 0xa55a) & 0xffff)",
                "trace_sha256_encoding","Concatenated source address u32LE followed by full callback result u32LE; reset each write call.",
                "scope","Captures the addresses passed to the bus callback, without inferring physical bus masking beyond this handler."),
            "cases",cases);
        for(Case c:inputs){cases.add(one(c));println("PASS "+c.name);}
        Files.writeString(output,new GsonBuilder().setPrettyPrinting().serializeNulls().create().toJson(fixture)+"\n");
        println("PASS "+cases.size()+" original native transfer sequences -> "+output);
    }
}

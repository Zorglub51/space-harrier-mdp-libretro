// Execute original m2engage MDP CPU read16/write16 callbacks on synthetic memory.
// @category SpaceHarrier
// Usage: -postScript MdpBusOracle.java /absolute/output.json
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

public class MdpBusOracle extends GhidraScript {
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
            byte[] writeCode = new byte[(int)(WRITE_END-WRITE_ENTRY)];
            currentProgram.getMemory().getBytes(toAddr(WRITE_ENTRY), writeCode);
            if (!WRITE_SHA256.equals(sha256(writeCode))) throw new IllegalStateException("Loaded write handler mismatch");
            writeMemory(toAddr(WRITE_ENTRY),writeCode);

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

    private static final String HANDLER_SHA256="81c6316adfba6adbc493dde4145b958137a8ea9af03b690b081c17ba785a32df";
    private static final String WRITE_SHA256="1e3eaa5d0d2338abd9b82c7363c61893e8b8f413555af321dcd1d753855a2efd";
    private static final long ENTRY=0xc0f74, CODE_END=0xc1058, WRITE_ENTRY=0xc086c, WRITE_END=0xc090c, ROM=0x21000000L;
    private String sha256(byte[] b)throws Exception{
        StringBuilder s=new StringBuilder();for(byte v:MessageDigest.getInstance("SHA-256").digest(b))s.append(String.format("%02x",v&255));return s.toString();
    }
    private RegisterValue thumbContext(){return new RegisterValue(currentProgram.getLanguage().getContextBaseRegister(),BigInteger.ZERO).combineValues(new RegisterValue(currentProgram.getRegister("TMode"),BigInteger.ONE));}
    private byte[] seed(int size,boolean ram){
        byte[] bytes=new byte[size];for(int i=0;i<size/2;i++){
            int value=ram?(i*37+0x5678)&65535:(i*11+(i>>>15)*0x123+0x1234)&65535;
            bytes[i*2]=(byte)value;bytes[i*2+1]=(byte)(value>>>8);
        }return bytes;
    }
    private OracleMachine machine(int romSize)throws Exception{
        OracleMachine e=new OracleMachine();init(e,ENTRY);
        e.writeMemory(toAddr(RAM),seed(0x20000,true));e.writeMemory(toAddr(ROM),seed(romSize,false));
        w32(e,CTX+8,RAM);w32(e,CTX+12,ROM);w32(e,CTX+16,romSize);return e;
    }
    private Map<String,Object> invoke(OracleMachine e,long entry,long source,int data)throws Exception{
        e.writeRegister("r0",CTX);e.writeRegister("r1",source);e.writeRegister("r2",data);
        e.writeRegister("lr",SENTINEL|1);e.writeRegister(e.getPCRegister(),entry);e.setContextRegister(thumbContext());
        int steps=0;List<Long> path=new ArrayList<>();
        while(e.getExecutionAddress().getOffset()!=SENTINEL){
            long pc=e.getExecutionAddress().getOffset();path.add(pc);
            if(!((pc>=ENTRY&&pc<CODE_END)||(pc>=WRITE_ENTRY&&pc<WRITE_END))||++steps>100)throw new IllegalStateException("unexpected pc "+Long.toHexString(pc));
            e.step(monitor);
        }
        if(reg(e,e.getStackPointerRegister().getName())!=STACK)throw new IllegalStateException("stack mismatch");
        return obj("result",reg(e,"r0"),"native_path",path);
    }
    private Map<String,Object> readCase(long source,int romSize)throws Exception{
        OracleMachine e=machine(romSize);
        return obj("kind","read16","source",source,"rom_size",romSize,"output",invoke(e,ENTRY,source,0));
    }
    private Map<String,Object> writeCase(long destination,int data)throws Exception{
        OracleMachine e=machine(65536);Map<String,Object> call=invoke(e,WRITE_ENTRY,destination,data);
        List<Object> reads=new ArrayList<>();
        for(long address:new long[]{destination,0xe00000|(destination&0x1fffe),0xfe0000,0xff0000,0xfffffe,0x1000000})
            reads.add(obj("address",address,"output",invoke(e,ENTRY,address,0)));
        return obj("kind","write16","destination",destination,"data",data,"output",call,"readbacks",reads,
            "ram_sha256",sha256(e.readMemory(toAddr(RAM),0x20000)),"rom_sha256",sha256(e.readMemory(toAddr(ROM),65536)));
    }
    public void run()throws Exception{
        if(getScriptArgs().length!=1)throw new IllegalArgumentException("Expected output JSON path");
        if(!BINARY_SHA256.equalsIgnoreCase(currentProgram.getExecutableSHA256()))throw new IllegalStateException("Private ELF SHA mismatch");
        List<Object> cases=new ArrayList<>();
        for(long address:new long[]{0,1,2,0xfffe,0x10000,0x1fffe,0x20000,0x1ffffe,0x200000,0x3ffffe,0x3fffff,
                0xe00000,0xe10000,0xfe0000,0xff0000,0xfffffc,0xfffffe,0x1000000,0x1000002,0x1010000,0x101fffe,0x1020000})
            cases.add(readCase(address,65536));
        for(long address:new long[]{0,0x7fffe,0x80000,0x17fffe,0x180000,0x37fffe,0x380000,0x3ffffe})
            cases.add(readCase(address,0x380000));
        for(long address:new long[]{0xe00000,0xe10000,0xfe0000,0xff0000,0xfffffe,0x1000000,0x1010000,0x1020000})
            cases.add(writeCase(address,0xabcd));
        Map<String,Object> fixture=obj("schema_version",1,"binary_sha256",BINARY_SHA256,
            "read16",obj("entry",ENTRY,"file_offset",ENTRY-0x10000,"sha256",HANDLER_SHA256),
            "write16",obj("entry",WRITE_ENTRY,"file_offset",WRITE_ENTRY-0x10000,"sha256",WRITE_SHA256),
            "execution_boundary","Original callback instructions through native return, no stubs. Only ROM and RAM branches exercised; no complete I/O or cartridge claim.",
            "callback_registration","C0CC6 resolves read callback C0F75; C0CC4 resolves write callback C086D. 94DC4 stores these at owner+8/+C. C2A00 stores owner in VDP+10.",
            "memory_encoding","Numeric u16 little-endian. RAM holds65536words/128KiB; the two64KiB banks have distinct seeds.",
            "ram_seed_word","(word_index*37+0x5678)&65535",
            "rom_seed_word","(word_index*11+(word_index>>15)*0x123+0x1234)&65535",
            "ram_size",131072,"cases",cases);
        Path output=Path.of(getScriptArgs()[0]);Files.createDirectories(output.toAbsolutePath().getParent());
        Files.writeString(output,new GsonBuilder().setPrettyPrinting().create().toJson(fixture)+"\n");println("PASS "+cases.size()+" original read16/write16 cases");
    }
}

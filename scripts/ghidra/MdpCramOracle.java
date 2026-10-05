// Execute m2engage's original MDP CRAM write decoder on synthetic input.
// @category SpaceHarrier
// Usage: -postScript MdpCramOracle.java /absolute/output.json
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

public class MdpCramOracle extends GhidraScript {
    private static final long HANDLER_FILE = 0x0b2ca8L;
    private static final long CODE_LENGTH = 0x620L;
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


    private Map<String, Object> one(Address entry, long address, long data, boolean direct) throws Exception {
        OracleMachine emu = new OracleMachine(entry);
        emu.writeMemory(toAddr(CTX), new byte[0x200]);
        emu.writeMemory(toAddr(STACK - 0x100), new byte[0x200]);
        emu.writeMemory(toAddr(RAM), new byte[256]);
        w32(emu, CTX, RAM);
        for (int r = 0; r < 13; r++) emu.writeRegister("r" + r, 0);
        for (String flag : new String[]{"CY", "ZR", "NG", "OV", "TB", "ISAModeSwitch"})
            if (currentProgram.getRegister(flag) != null) emu.writeRegister(flag, 0);
        emu.writeRegister("r0", CTX);
        emu.writeRegister("r1", address);
        emu.writeRegister("r2", data);
        emu.writeRegister(emu.getStackPointerRegister(), STACK);
        emu.writeRegister("lr", SENTINEL | 1);
        emu.writeRegister(emu.getPCRegister(), entry.getOffset());
        RegisterValue context = new RegisterValue(currentProgram.getLanguage().getContextBaseRegister(), BigInteger.ZERO);
        context = context.combineValues(new RegisterValue(currentProgram.getRegister("TMode"), BigInteger.ONE));
        emu.setContextRegister(context);
        int steps = 0;
        List<String> path = new ArrayList<>();
        // Non-direct accesses stop before normal VDP dispatch. Direct accesses
        // execute the original store and return, including stack restoration.
        while (emu.getExecutionAddress().getOffset() != SENTINEL &&
                !emu.getExecutionAddress().equals(entry.add(0x3c)) && steps++ < 200) {
            path.add(emu.getExecutionAddress().toString());
            emu.step(monitor);
        }
        if (steps >= 200) throw new IllegalStateException("step limit");
        boolean returned = emu.getExecutionAddress().getOffset() == SENTINEL;
        if (returned != direct) throw new IllegalStateException("unexpected dispatch path");
        byte[] cram = emu.readMemory(toAddr(RAM), 256);
        List<Object> writes = new ArrayList<>();
        for (int index = 0; index < 128; index++) {
            int value = (cram[2 * index] & 255) | ((cram[2 * index + 1] & 255) << 8);
            if (value != 0) writes.add(obj("index", index, "value", value));
        }
        if (direct && (writes.size() != 1 ||
                reg(emu, emu.getStackPointerRegister().getName()) != STACK))
            throw new IllegalStateException("unexpected write or stack state");
        if (!direct && !writes.isEmpty()) throw new IllegalStateException("non-direct CRAM write");
        return obj("input", obj("byte_address", address, "data", data),
            "output", obj("direct_cram", direct, "cram_writes", writes),
            "native_instruction_steps", steps, "instruction_addresses", path);
    }

    @Override public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 1) throw new IllegalArgumentException("usage: output.json");
        if (!BINARY_SHA256.equalsIgnoreCase(currentProgram.getExecutableSHA256()))
            throw new IllegalArgumentException("Unexpected m2engage binary hash");
        List<Address> addresses = currentProgram.getMemory().locateAddressesForFileOffset(HANDLER_FILE);
        if (addresses.size() != 1) throw new IllegalStateException("Ambiguous handler mapping");
        Address entry = addresses.get(0);
        byte[] bytes = new byte[4];
        currentProgram.getMemory().getBytes(entry, bytes);
        if (!Arrays.equals(bytes, new byte[]{0x2d, (byte)0xe9, (byte)0xf0, 0x4f}))
            throw new IllegalStateException("Unexpected MDP handler entry bytes");
        List<Object> cases = new ArrayList<>();
        for (long[] sample : new long[][]{{0xc00400, 0x0eee}, {0xc00402, 0x0222},
                {0xc00462, 0x0ce6}, {0xc0047e, 0x0468}, {0xc00480, 0x0ace},
                {0xc004fe, 0x1357}, {0xc00462, 0xffff}})
            cases.add(one(entry, sample[0], sample[1], true));
        for (long address : new long[]{0xc003fe, 0xc00500, 0xc00662})
            cases.add(one(entry, address, 0x0abc, false));
        Map<String, Object> result = obj("schema", 1, "source", obj(
            "binary_sha256", BINARY_SHA256, "handler_file_offset", HANDLER_FILE,
            "handler_loaded_address", entry.getOffset(),
            "engine", "Ghidra PcodeEmulator ARM p-code", "ghidra_version",
            ghidra.framework.Application.getApplicationVersion(), "execution_boundary",
            "Original return for direct CRAM, before normal port dispatch for other addresses"),
            "cases", cases);
        Path output = Path.of(args[0]);
        if (output.toAbsolutePath().getParent() != null)
            Files.createDirectories(output.toAbsolutePath().getParent());
        Files.writeString(output, new GsonBuilder().setPrettyPrinting().create().toJson(result)
            + "\n", StandardCharsets.UTF_8);
        println("Wrote " + cases.size() + " original ARM CRAM decoder cases to " + output);
    }
}

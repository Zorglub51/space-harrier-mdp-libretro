// Execute the original M2 ARM Thumb collision hook and export replayable cases.
// @category SpaceHarrier
// Usage: -postScript Sh1CollisionOracle.java /absolute/output.json
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

public class Sh1CollisionOracle extends GhidraScript {
    private static final long HANDLER_FILE = 0x0d57c4L;
    private static final long TAIL_BRANCH_OFFSET = 0x62L;
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
            byte[] code = new byte[(int)TAIL_BRANCH_OFFSET + 2];
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

    private Map<String, Object> one(Address entry, String name, int depthA4,
            int depthA2, long a2, long a4, long ticks, int flags, int x) throws Exception {
        long d1 = 0x11223344L, d4 = 0x55667788L, d6 = 0x99aabb05L, a0 = 0xddeeff01L;
        long address2 = (a2 + 10) & 0xfffffeL;
        long address4 = (a4 + 10) & 0xfffffeL;
        if (address2 == address4 && depthA2 != depthA4)
            throw new IllegalArgumentException("Inconsistent aliased memory case");
        List<Object> memory = new ArrayList<>();
        memory.add(obj("address", address2, "value", depthA2 & 65535));
        if (address4 != address2)
            memory.add(obj("address", address4, "value", depthA4 & 65535));
        Map<String, Object> input = obj("d1", d1, "d4", d4, "d6", d6,
            "a0", a0, "a2", a2 & MASK32, "a4", a4 & MASK32,
            "flags", flags, "x", x, "ticks", ticks & MASK32,
            "memory_words", memory);
        OracleMachine emu = new OracleMachine(entry);
        try {
            // Explicit initialization prevents accidental dependence on Ghidra's
            // uninitialized-memory defaults. Memory is M2's little-endian word store.
            emu.writeMemory(toAddr(CTX), new byte[0x1000]);
            emu.writeMemory(toAddr(STACK - 0x100), new byte[0x200]);
            for (int page = 0; page < 256; page++)
                w32(emu, CTX + 0x1d0 + 4L * page, RAM + 0x10000L * page);
            w32(emu, CTX + 0x2c, d1);
            w32(emu, CTX + 0x38, d4);
            w32(emu, CTX + 0x40, d6);
            w32(emu, CTX + 0x48, a0);
            w32(emu, CTX + 0x50, a2);
            w32(emu, CTX + 0x58, a4);
            w32(emu, CTX + 0x84, SENTINEL | 1);
            emu.writeMemoryValue(toAddr(CTX + 0x1e), 1, flags);
            emu.writeMemoryValue(toAddr(CTX + 0x1f), 1, x);
            emu.writeMemoryValue(toAddr(RAM + address2), 2, depthA2 & 65535);
            emu.writeMemoryValue(toAddr(RAM + address4), 2, depthA4 & 65535);
            byte[] before = emu.readMemory(toAddr(CTX), 0x1000);
            for (int r = 0; r < 13; r++) emu.writeRegister("r" + r, 0);
            for (String flag : new String[]{"CY", "ZR", "NG", "OV", "TB", "ISAModeSwitch"})
                if (currentProgram.getRegister(flag) != null) emu.writeRegister(flag, 0);
            emu.writeRegister("r0", CTX);
            emu.writeRegister("r1", ticks & MASK32);
            emu.writeRegister(emu.getStackPointerRegister(), STACK);
            emu.writeRegister("lr", SENTINEL | 1);
            emu.writeRegister(emu.getPCRegister(), entry.getOffset());
            RegisterValue context = new RegisterValue(
                currentProgram.getLanguage().getContextBaseRegister(), BigInteger.ZERO);
            context = context.combineValues(new RegisterValue(
                currentProgram.getRegister("TMode"), BigInteger.ONE));
            emu.setContextRegister(context);
            // Stop at the original terminal BX r3, after POP and every observable
            // effect. Its bytes and destination are verified separately below;
            // executing the dispatcher is outside this hook's contract.
            Address tailBranch = entry.add(TAIL_BRANCH_OFFSET);
            int steps = 0;
            while (!emu.getExecutionAddress().equals(tailBranch) && steps++ < 100) {
                if (!emu.step(monitor))
                    throw new IllegalStateException(name + " at " + emu.getExecutionAddress()
                        + ": " + emu.getLastError());
            }
            if (!emu.getExecutionAddress().equals(tailBranch))
                throw new IllegalStateException("Instruction limit in " + name);
            Map<String, Object> output = obj("d1", u32(emu, CTX + 0x2c),
                "d4", u32(emu, CTX + 0x38), "d6", u32(emu, CTX + 0x40),
                "a0", u32(emu, CTX + 0x48),
                "flags", emu.readMemoryByte(toAddr(CTX + 0x1e)) & 255,
                "x", emu.readMemoryByte(toAddr(CTX + 0x1f)) & 255,
                "next_pc", reg(emu, "r2"), "ticks", reg(emu, "r1"));
            if (reg(emu, "r0") != CTX || reg(emu, "r3") != (SENTINEL | 1)
                    || reg(emu, emu.getStackPointerRegister().getName()) != STACK)
                throw new IllegalStateException("Broken native calling convention in " + name);
            byte[] after = emu.readMemory(toAddr(CTX), 0x1000);
            List<Integer> changedOffsets = new ArrayList<>();
            for (int i = 0; i < after.length; i++)
                if (after[i] != before[i]) changedOffsets.add(i);
            return obj("name", name, "input", input, "output", output,
                "native_instruction_steps", steps, "changed_state_byte_offsets", changedOffsets,
                "stop_before_tail_branch", tailBranch.getOffset());
        } finally {
            emu.dispose();
        }
    }

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length != 1) throw new IllegalArgumentException("usage: output.json");
        if (!BINARY_SHA256.equalsIgnoreCase(currentProgram.getExecutableSHA256()))
            throw new IllegalArgumentException("Unexpected m2engage binary hash");
        List<Address> addresses = currentProgram.getMemory().locateAddressesForFileOffset(HANDLER_FILE);
        if (addresses.size() != 1) throw new IllegalStateException("Ambiguous handler file mapping");
        Address entry = addresses.get(0);
        byte[] signature = new byte[8];
        currentProgram.getMemory().getBytes(entry, signature);
        if (!Arrays.equals(signature, new byte[]{0x30, (byte)0xb4, 0x03, 0x46,
                0x00, 0x6d, (byte)0x9a, 0x6d}))
            throw new IllegalStateException("Unexpected handler entry bytes");
        byte[] tailBytes = new byte[2];
        currentProgram.getMemory().getBytes(entry.add(TAIL_BRANCH_OFFSET), tailBytes);
        if (!Arrays.equals(tailBytes, new byte[]{0x18, 0x47}))
            throw new IllegalStateException("Expected terminal BX r3");
        println("Original Thumb handler file " + Long.toHexString(HANDLER_FILE)
            + " mapped at " + entry);
        List<Object> cases = new ArrayList<>();
        int[] depths = {0, 1, 0x7fff, 0x8000, 0xffff};
        for (int a = 0; a < depths.length; a++)
            for (int b = 0; b < depths.length; b++)
                cases.add(one(entry, String.format("depth_%04x_%04x", depths[a], depths[b]),
                    depths[a], depths[b], 0xff2200L, 0xff2254L,
                    12345, 15, (a + b) % 2));
        cases.add(one(entry, "ticks_wrap", 0x700, 0x100,
            0xff2200L, 0xff2254L, 0xfffffff0L, 15, 1));
        cases.add(one(entry, "odd_addresses", 0xffff, 0x8000,
            0xff2201L, 0xff2255L, 0, 0, 1));
        cases.add(one(entry, "high_address_alias", 0x4321, 0x1234,
            0x12ff2200L, 0xabff2254L, 0, 15, 0));
        cases.add(one(entry, "same_aliased_word", 5, 5,
            0x00ff2200L, 0x12ff2200L, 0, 15, 1));
        cases.add(one(entry, "address_add_wrap", 0, 0xffff,
            0xfffffff8L, 0xff2254L, 0, 15, 1));
        cases.add(one(entry, "page_crossing", 0x8000, 0x7fff,
            0x00fefff8L, 0x00ffffffL, 0, 0, 0));
        Map<String, Object> result = obj("schema", 1, "source", obj(
            "binary_sha256", BINARY_SHA256, "handler_file_offset", HANDLER_FILE,
            "handler_loaded_address", entry.getOffset(), "guest_hook_pc", 0x19b93e,
            "engine", "Ghidra PcodeEmulator ARM p-code", "ghidra_version",
            ghidra.framework.Application.getApplicationVersion(), "execution_boundary",
            "Before original terminal BX r3; branch bytes, destination, and restored stack verified"),
            "cases", cases);
        Path output = Path.of(args[0]);
        if (output.toAbsolutePath().getParent() != null)
            Files.createDirectories(output.toAbsolutePath().getParent());
        Files.writeString(output, new GsonBuilder().setPrettyPrinting().create().toJson(result)
            + "\n", StandardCharsets.UTF_8);
        println("Wrote " + cases.size() + " original ARM oracle cases to " + output);
    }
}

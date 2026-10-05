// Execute the original M2 ARM Thumb line-phase hook and export replayable cases.
// @category SpaceHarrier
// Usage: -postScript Sh2LineOracle.java /absolute/output.json
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

public class Sh2LineOracle extends GhidraScript {
    private static final long HANDLER_FILE = 0x0bf174L;
    private static final long TAIL_BRANCH_OFFSET = 0xdcL;
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


    private Map<String, Object> one(Address entry, String name, long d0,
            long d1, long d4, long limit, long a0, long ticks) throws Exception {
        int flags = 15, x = 31;
        OracleMachine emu = new OracleMachine(entry);
        try {
            emu.writeMemory(toAddr(CTX), new byte[0x1200]);
            emu.writeMemory(toAddr(STACK - 0x100), new byte[0x200]);
            for (int r = 0; r < 8; r++) {
                w32(emu, CTX + 0x28 + r * 4, 0xabc00000L + r);
                w32(emu, CTX + 0x48 + r * 4, 0xdef00000L + r);
            }
            // This SH2 handler reads the flat word-swapped memory base, unlike
            // the page-table accesses of the SH1 collision reference.
            w32(emu, CTX + 0x11dc, RAM);
            w32(emu, CTX + 0x28, d0);
            w32(emu, CTX + 0x2c, d1);
            w32(emu, CTX + 0x38, d4);
            w32(emu, CTX + 0x48, a0);
            w32(emu, CTX + 0x84, SENTINEL | 1);
            emu.writeMemoryValue(toAddr(CTX + 0x1e), 1, flags);
            emu.writeMemoryValue(toAddr(CTX + 0x1f), 1, x);
            emu.writeMemoryValue(toAddr(RAM + 0xff116a), 2, limit >>> 16);
            emu.writeMemoryValue(toAddr(RAM + 0xff116c), 2, limit & 65535);
            byte[] before = emu.readMemory(toAddr(CTX), 0x1200);
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
            Address loopExit = entry.add(0xca), doneExit = entry.add(0xdc);
            int steps = 0;
            while (!emu.getExecutionAddress().equals(loopExit)
                    && !emu.getExecutionAddress().equals(doneExit) && steps++ < 200)
                emu.step(monitor);
            if (steps >= 200) throw new IllegalStateException("Instruction limit in " + name);
            if (reg(emu, "r0") != CTX || reg(emu, "r3") != (SENTINEL | 1)
                    || reg(emu, emu.getStackPointerRegister().getName()) != STACK)
                throw new IllegalStateException("Broken native calling convention in " + name);
            byte[] after = emu.readMemory(toAddr(CTX), 0x1200);
            List<Integer> changedOffsets = new ArrayList<>();
            for (int i = 0; i < after.length; i++)
                if (after[i] != before[i]) changedOffsets.add(i);
            return obj("name", name,
                "input", obj("d0", d0, "d1", d1, "d4", d4, "a0", a0,
                    "limit_ff116a", limit, "flags", flags, "x", x, "ticks", ticks),
                "output", obj("d0", u32(emu, CTX + 0x28), "d1", u32(emu, CTX + 0x2c),
                    "d4", u32(emu, CTX + 0x38), "a0", u32(emu, CTX + 0x48),
                    "a2", u32(emu, CTX + 0x50), "a3", u32(emu, CTX + 0x54),
                    "flags", emu.readMemoryByte(toAddr(CTX + 0x1e)) & 255,
                    "x", emu.readMemoryByte(toAddr(CTX + 0x1f)) & 255,
                    "next_pc", reg(emu, "r2"), "ticks", reg(emu, "r1")),
                "native_instruction_steps", steps,
                "changed_state_byte_offsets", changedOffsets,
                "stop_before_original_bx_r3", emu.getExecutionAddress().getOffset());
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
        if (addresses.size() != 1) throw new IllegalStateException("Ambiguous handler mapping");
        Address entry = addresses.get(0);
        byte[] bytes = new byte[4];
        currentProgram.getMemory().getBytes(entry, bytes);
        if (!Arrays.equals(bytes, new byte[]{0x2d, (byte)0xe9, (byte)0xf0, 0x43}))
            throw new IllegalStateException("Unexpected handler entry bytes");
        for (long offset : new long[]{0xca, 0xdc}) {
            byte[] tail = new byte[2];
            currentProgram.getMemory().getBytes(entry.add(offset), tail);
            if (!Arrays.equals(tail, new byte[]{0x18, 0x47}))
                throw new IllegalStateException("Expected original terminal BX r3");
        }
        List<Object> cases = new ArrayList<>();
        long[] positions = {0, 0xbe, 0xbf, 0xc0, 0x7fffffffL, 0x80000000L, 0xfffffffeL, 0xffffffffL};
        long[] limits = {0x100, 0x80000040L, 0, 0xffffffffL};
        long[] phases = {0xffffffe0L, 0x55667788L, 0x87654321L, 0};
        for (int i = 0; i < positions.length; i++)
            for (int j = 0; j < limits.length; j++)
                cases.add(one(entry, String.format("position_%08x_limit_%08x", positions[i], limits[j]),
                    positions[i], 0x11223344L, phases[j], limits[j], 0xff5000, 100));
        cases.add(one(entry, "address_and_ticks_wrap", 0, 0, 0xffffffe0L,
            0x100, 0xfffffff8L, 0xfffffff0L));
        Map<String, Object> result = obj("schema", 1, "source", obj(
            "binary_sha256", BINARY_SHA256, "handler_file_offset", HANDLER_FILE,
            "handler_loaded_address", entry.getOffset(), "guest_hook_pc", 0x18bcf4,
            "engine", "Ghidra PcodeEmulator ARM p-code", "ghidra_version",
            ghidra.framework.Application.getApplicationVersion(), "execution_boundary",
            "Before either original BX r3; branch bytes, dispatcher target and restored stack verified"),
            "cases", cases);
        Path output = Path.of(args[0]);
        if (output.toAbsolutePath().getParent() != null)
            Files.createDirectories(output.toAbsolutePath().getParent());
        Files.writeString(output, new GsonBuilder().setPrettyPrinting().create().toJson(result)
            + "\n", StandardCharsets.UTF_8);
        println("Wrote " + cases.size() + " original ARM oracle cases to " + output);
    }
}

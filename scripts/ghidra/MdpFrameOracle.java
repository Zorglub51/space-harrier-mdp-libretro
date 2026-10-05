// Execute the original M2 renderer through indexed composition on captured video state.
// @category SpaceHarrier
// Usage: -postScript MdpFrameOracle.java INPUT_DIR OUTPUT_DIR all|LINE[,LINE...] [before|after]
// See docs/MDP_FRAME_ORACLE.md. No game assets are included by this script.
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

public class MdpFrameOracle extends GhidraScript {
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

    private Map<String, Object> one(Path snapshot, Path output, int line,
            boolean afterMdp) throws Exception {
        String prefix = String.format("line-%03d", line);
        Map<String, Object> hashes = new LinkedHashMap<>();
        OracleMachine emu = new OracleMachine();
        init(emu, RENDER_ENTRY);
        emu.writeMemory(toAddr(STACK - 0x4000), new byte[0x5000]);
        emu.writeMemory(toAddr(RAM), input(snapshot,
            prefix + "-before-m_vram.bin", 0x10000, hashes));
        emu.writeMemory(toAddr(RAM + 0x10000), input(snapshot,
            prefix + (afterMdp ? "-after-" : "-before-") + "m_mdp_ram.bin",
            0x10000, hashes));

        final long cram = CTX + 0x1000, vsram = CTX + 0x1200;
        final long destination = CTX + 0x2000, destinationPointer = CTX + 0x1300;
        // The core applies pending raster CRAM writes immediately before drawing.
        emu.writeMemory(toAddr(cram), input(snapshot,
            prefix + "-after-m_cram.bin", 256, hashes));
        byte[] vs = input(snapshot, prefix + "-before-m_vsram.bin", 128, hashes);
        byte[] nativeVs = new byte[128];
        // M2's port decoder reserves two leading VSRAM words and mirrors its
        // first two global values. This adapts storage, not rendering behavior.
        for (int index = 0; index < 64; index++) {
            int target = (index + 2) & 63;
            nativeVs[target * 2] = vs[index * 2];
            nativeVs[target * 2 + 1] = vs[index * 2 + 1];
        }
        System.arraycopy(vs, 0, nativeVs, 0, 4);
        emu.writeMemory(toAddr(vsram), nativeVs);

        byte[] registerWords = input(snapshot,
            prefix + "-before-m_regs.bin", 128, hashes);
        byte[] registers = new byte[64];
        for (int index = 0; index < 64; index++) registers[index] = registerWords[index * 2];
        emu.writeMemory(toAddr(CTX + 0x14), registers);
        w32(emu, CTX, cram);
        w32(emu, CTX + 4, RAM);
        w32(emu, CTX + 8, vsram);
        int activeWidth = (registers[12] & 0x81) == 0x81 ? 320 : 256;
        // Original M2 line-clock initialization at C32C8.
        w32(emu, CTX + 0x60, FRAME_WIDTH);
        w32(emu, CTX + 0x64, 240);
        w32(emu, CTX + 0x68, activeWidth);
        w32(emu, CTX + 0x6c, ACTIVE_HEIGHT);
        w32(emu, destinationPointer, destination);
        emu.writeMemory(toAddr(destination), new byte[FRAME_WIDTH * 2]);
        emu.writeRegister("r0", CTX);
        emu.writeRegister("r1", line);
        emu.writeRegister("r2", destinationPointer);

        int instructions = 0, memsetCalls = 0;
        boolean captured = false, intermediateBuffers = false;
        // Avoid stale diagnostic files if a previously active line is replayed
        // with display disabled in the same output directory.
        for (String suffix : new String[]{"indices.bin", "native-planes-u16le.bin",
                "native-sprites-u16le.bin", "failure.txt"})
            Files.deleteIfExists(output.resolve("line-" + line + "-" + suffix));
        try {
            while (instructions++ < MAX_INSTRUCTIONS) {
                long pc = emu.getExecutionAddress().getOffset();
                if (pc == MEMSET_ENTRY) {
                    long pointer = reg(emu, "r0"), size = reg(emu, "r2");
                    if (size > 0x2000 || pointer < STACK - 0x4000
                            || pointer + size > STACK + 0x1000)
                        throw new IllegalStateException("Unexpected memset range");
                    byte[] bytes = new byte[(int) size];
                    Arrays.fill(bytes, (byte) reg(emu, "r1"));
                    emu.writeMemory(toAddr(pointer), bytes);
                    long returnAddress = reg(emu, "lr");
                    if ((returnAddress & 1) == 0)
                        throw new IllegalStateException("Expected Thumb memset caller");
                    emu.writeRegister(emu.getPCRegister(), returnAddress & ~1L);
                    emu.setContextRegister(thumbContext());
                    memsetCalls++;
                    continue;
                }
                if (pc == COMPOSITE_ENTRY) {
                    intermediateBuffers = true;
                    long sp = reg(emu, emu.getStackPointerRegister().getName());
                    Files.write(output.resolve("line-" + line + "-native-planes-u16le.bin"),
                        emu.readMemory(toAddr(sp + 0x2c4), activeWidth * 2));
                    Files.write(output.resolve("line-" + line + "-native-sprites-u16le.bin"),
                        emu.readMemory(toAddr(sp + 0x678), activeWidth * 2));
                }
                if (pc == PALETTE_ENTRY) {
                    long sp = reg(emu, emu.getStackPointerRegister().getName());
                    Files.write(output.resolve("line-" + line + "-indices.bin"),
                        emu.readMemory(toAddr(sp + 0xe8), FRAME_WIDTH));
                    captured = true;
                    break;
                }
                if (pc < 0xc1000 || pc >= 0xc3500)
                    throw new IllegalStateException("Unexpected native call at "
                        + Long.toHexString(pc));
                emu.step(monitor);
            }
            if (!captured) throw new IllegalStateException("Instruction limit reached");
            Map<String, Object> result = obj("success", true, "line", line,
                "binary_sha256", BINARY_SHA256, "entry", RENDER_ENTRY,
                "stop_before", PALETTE_ENTRY, "engine", "Ghidra PcodeEmulator original ARM",
                "boundary", "After original indexed composition, before NEON palette conversion",
                "framebuffer_width", FRAME_WIDTH, "active_width", activeWidth,
                "active_x_offset", (FRAME_WIDTH - activeWidth) / 2,
                "instructions", instructions, "memset_calls", memsetCalls,
                "intermediate_buffers_captured", intermediateBuffers,
                "mdp_state", afterMdp ? "after" : "before", "input_sha256", hashes);
            Files.writeString(output.resolve("line-" + line + ".json"),
                new GsonBuilder().setPrettyPrinting().create().toJson(result) + "\n");
            println("PASS original C1E24 indexed line " + line + ", " + instructions + " steps");
            return result;
        } catch (Exception error) {
            Files.writeString(output.resolve("line-" + line + "-failure.txt"),
                "PC=" + emu.getExecutionAddress() + " steps=" + instructions
                + " memset_calls=" + memsetCalls + "\n" + error + "\n");
            throw error;
        }
    }

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 3 || args.length > 4)
            throw new IllegalArgumentException(
                "usage: INPUT_DIR OUTPUT_DIR all|LINE[,LINE...] [before|after]");
        if (!BINARY_SHA256.equalsIgnoreCase(currentProgram.getExecutableSHA256()))
            throw new IllegalArgumentException("Unexpected m2engage binary SHA256");
        List<Address> entries = currentProgram.getMemory().locateAddressesForFileOffset(0xb1e24);
        if (entries.size() != 1 || entries.get(0).getOffset() != RENDER_ENTRY)
            throw new IllegalArgumentException("Import ELF at its original virtual addresses");
        boolean afterMdp = args.length == 4 && args[3].equals("after");
        if (args.length == 4 && !afterMdp && !args[3].equals("before"))
            throw new IllegalArgumentException("MDP state must be before or after");
        Path snapshot = Path.of(args[0]), output = Path.of(args[1]);
        Files.createDirectories(output);
        List<Integer> lines = new ArrayList<>();
        if (args[2].equals("all")) {
            for (int line = 0; line < ACTIVE_HEIGHT; line++)
                if (Files.exists(snapshot.resolve(String.format("line-%03d-before-m_vram.bin", line))))
                    lines.add(line);
        } else {
            for (String part : args[2].split(",")) {
                int line = Integer.parseInt(part);
                if (line < 0 || line >= ACTIVE_HEIGHT)
                    throw new IllegalArgumentException("Visible line outside 0..223");
                lines.add(line);
            }
        }
        if (lines.isEmpty()) throw new IllegalArgumentException("No captured lines found");
        List<Object> results = new ArrayList<>();
        for (int line : lines) results.add(one(snapshot, output, line, afterMdp));
        Files.writeString(output.resolve("run.json"),
            new GsonBuilder().setPrettyPrinting().create().toJson(obj(
                "schema", 1, "snapshot_directory", snapshot.toAbsolutePath().toString(),
                "complete_visible_frame", args[2].equals("all") && lines.size() == ACTIVE_HEIGHT,
                "ghidra_version", ghidra.framework.Application.getApplicationVersion(),
                "lines", results)) + "\n");
    }
}

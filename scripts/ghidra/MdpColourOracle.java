// Execute the original MDP RGB4440 colour callback on synthetic pixel words.
// @category SpaceHarrier
// Usage: -postScript MdpColourOracle.java /absolute/output.json
// Import m2engage without analysis. No game data or original code is exported.
import ghidra.app.script.GhidraScript;
import ghidra.app.plugin.processors.sleigh.SleighLanguage;
import ghidra.pcode.emu.PcodeEmulator;
import ghidra.pcode.emu.PcodeThread;
import ghidra.pcode.exec.PcodeExecutorStatePiece.Reason;
import ghidra.program.model.address.Address;
import ghidra.program.model.lang.Register;
import ghidra.program.model.lang.RegisterValue;
import com.google.gson.GsonBuilder;
import java.math.BigInteger;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.ArrayList;
import java.util.Arrays;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public class MdpColourOracle extends GhidraScript {
    private static final long CALLBACK_FILE = 0x219e08L;
    private static final long OUTPUT = 0x10000000L;
    private static final long STACK = 0x20001000L;
    private static final long RETURN = 0x30000000L;
    private static final String BINARY_SHA256 =
        "2374ddca2241d2a040f587a1e86359c3d3d5f1dc93e566588b35e15bee73178f";
    private PcodeEmulator machine;
    private PcodeThread<byte[]> thread;
    private Address entry;

    private static Map<String, Object> obj(Object... pairs) {
        Map<String, Object> result = new LinkedHashMap<>();
        for (int i = 0; i < pairs.length; i += 2) result.put((String)pairs[i], pairs[i + 1]);
        return result;
    }
    private byte[] le(long value, int size) {
        byte[] bytes = new byte[size];
        for (int i = 0; i < size; i++) bytes[i] = (byte)(value >>> (8 * i));
        return bytes;
    }
    private void reg(String name, long value) {
        Register register = currentProgram.getRegister(name);
        thread.getState().setVar(register, le(value, register.getMinimumByteSize()));
    }
    private long reg(String name) {
        byte[] bytes = thread.getState().getVar(currentProgram.getRegister(name), Reason.INSPECT);
        long value = 0;
        for (int i = 0; i < bytes.length; i++) value |= ((long)bytes[i] & 255) << (8 * i);
        return value & 0xffffffffL;
    }
    private int convert(long raw) throws Exception {
        byte[] guard = new byte[16]; Arrays.fill(guard, (byte)0xa5);
        machine.getSharedState().setVar(toAddr(OUTPUT), guard.length, true, guard);
        for (int i = 0; i < 13; i++) reg("r" + i, 0);
        reg("r0", raw); reg("r1", OUTPUT); reg("r4", 0x12345678); reg("r5", 0x87654321L);
        reg(currentProgram.getCompilerSpec().getStackPointer().getName(), STACK);
        reg("lr", RETURN | 1);
        thread.overrideCounter(entry);
        RegisterValue context = new RegisterValue(currentProgram.getLanguage().getContextBaseRegister(), BigInteger.ZERO);
        thread.overrideContext(context.combineValues(new RegisterValue(currentProgram.getRegister("TMode"), BigInteger.ONE)));
        int steps = 0;
        while (thread.getCounter().getOffset() != RETURN && steps++ < 100) {
            monitor.checkCancelled(); thread.stepInstruction();
        }
        if (steps >= 100 || reg("r0") != 1 || reg("r4") != 0x12345678L || reg("r5") != 0x87654321L)
            throw new IllegalStateException("Native callback return/ABI failure for " + raw);
        byte[] out = machine.getSharedState().getVar(toAddr(OUTPUT), 16, true, Reason.INSPECT);
        for (int i = 0; i < out.length; i++)
            if ((i < 4 || i > 6) && out[i] != (byte)0xa5)
                throw new IllegalStateException("Output guard overwritten at " + i);
        return ((out[4] & 255) << 16) | ((out[5] & 255) << 8) | (out[6] & 255);
    }
    @Override public void run() throws Exception {
        if (getScriptArgs().length != 1) throw new IllegalArgumentException("usage: output.json");
        if (!BINARY_SHA256.equalsIgnoreCase(currentProgram.getExecutableSHA256()))
            throw new IllegalArgumentException("Unexpected m2engage SHA256");
        List<Address> entries = currentProgram.getMemory().locateAddressesForFileOffset(CALLBACK_FILE);
        if (entries.size() != 1) throw new IllegalStateException("Ambiguous callback mapping");
        entry = entries.get(0);
        byte[] code = new byte[0x2a]; currentProgram.getMemory().getBytes(entry, code);
        if (!Arrays.equals(Arrays.copyOf(code, 4), new byte[]{2, 0x46, 0x11, 0x23}))
            throw new IllegalArgumentException("Unexpected callback entry");
        machine = new PcodeEmulator((SleighLanguage)currentProgram.getLanguage());
        thread = machine.newThread();
        machine.getSharedState().setVar(entry, code.length, true, code);
        machine.getSharedState().setVar(toAddr(STACK - 0x100), 0x200, true, new byte[0x200]);
        List<Integer> colours = new ArrayList<>();
        for (int rgb444 = 0; rgb444 < 4096; rgb444++) colours.add(convert(rgb444 << 4));
        List<Object> ignored = new ArrayList<>();
        for (int low = 0; low < 16; low++)
            ignored.add(obj("input", 0x1350 | low, "rgb888", convert(0x1350 | low)));
        for (long raw : new long[]{0xffff0000L, 0xfffffff0L, 0xabcd135fL})
            ignored.add(obj("input", raw, "rgb888", convert(raw)));
        Map<String, Object> source = obj("binary_sha256", BINARY_SHA256,
            "callback_file_offset", CALLBACK_FILE, "callback_loaded_address", entry.getOffset(),
            "engine", "Ghidra PcodeEmulator ARM p-code",
            "ghidra_version", ghidra.framework.Application.getApplicationVersion(),
            "execution_boundary", "Original registered MDP colour callback entry through native return",
            "input_encoding", "RGB4440 word; rgb888_by_rgb444 index is input >> 4",
            "output_encoding", "R << 16 | G << 8 | B, read from callback output bytes +4/+5/+6",
            "presentation_boundary", "Emulator colour conversion before host GPU presentation; filters are outside this oracle");
        Files.writeString(Path.of(getScriptArgs()[0]), new GsonBuilder().setPrettyPrinting().create().toJson(
            obj("schema", 1, "source", source, "rgb888_by_rgb444", colours, "ignored_bits", ignored)) + "\n");
        println("PASS " + (colours.size() + ignored.size()) + " original MDP colour callback cases");
    }
}

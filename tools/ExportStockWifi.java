// Local-only stock firmware analysis. Never executes firmware or device APIs.
// Script arguments: output directory, optional comma-separated entry addresses.
//@category Walkman.Research
import ghidra.app.script.GhidraScript;
import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.program.model.address.Address;
import ghidra.program.model.listing.Function;
import ghidra.program.model.symbol.Symbol;
import ghidra.program.model.symbol.SymbolIterator;
import ghidra.program.model.symbol.Reference;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.charset.StandardCharsets;
import java.util.TreeMap;
import java.util.Map;

public class ExportStockWifi extends GhidraScript {
    @Override public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 1) throw new IllegalArgumentException("Output directory required");
        Path out = Path.of(args[0]);
        Files.createDirectories(out);
        Map<String, Function> functions = new TreeMap<>();
        StringBuilder references = new StringBuilder("target\tfrom\tcaller\n");
        SymbolIterator symbols = currentProgram.getSymbolTable().getAllSymbols(true);
        while (symbols.hasNext() && !monitor.isCancelled()) {
            Symbol symbol = symbols.next();
            String name = symbol.getName();
            if (!(name.startsWith("cnmgr_") || name.startsWith("yal_") || name.startsWith("salc_curl_"))) continue;
            for (Reference ref : getReferencesTo(symbol.getAddress())) {
                Function caller = getFunctionContaining(ref.getFromAddress());
                references.append(name).append('\t').append(ref.getFromAddress()).append('\t')
                    .append(caller == null ? "no_function" : caller.getEntryPoint()).append('\n');
                if (caller != null) functions.put(caller.getEntryPoint().toString(), caller);
            }
        }
        if (args.length > 1) for (String value : args[1].split(",")) {
            Address address = toAddr(Long.parseUnsignedLong(value.replace("0x", ""), 16));
            Function function = getFunctionAt(address);
            if (function == null) {
                Function containing = getFunctionContaining(address);
                if (containing != null) throw new IllegalArgumentException("Interior address " + value + " belongs to " + containing.getEntryPoint());
                disassemble(address);
                function = createFunction(address, null);
            }
            if (function == null) throw new IllegalStateException("No function at " + value);
            functions.put(function.getEntryPoint().toString(), function);
        }
        Files.writeString(out.resolve("references.tsv"), references, StandardCharsets.UTF_8);
        StringBuilder edges = new StringBuilder("target\tfrom\tcaller\ttype\n");
        Map<String, Function> callers = new TreeMap<>();
        for (Function target : functions.values()) for (Reference ref : getReferencesTo(target.getEntryPoint())) {
            Function caller = getFunctionContaining(ref.getFromAddress());
            edges.append(target.getEntryPoint()).append('\t').append(ref.getFromAddress()).append('\t')
                .append(caller == null ? "no_function" : caller.getEntryPoint()).append('\t').append(ref.getReferenceType()).append('\n');
            if (args.length > 2 && args[2].equals("callers") && caller != null) callers.put(caller.getEntryPoint().toString(), caller);
        }
        functions.putAll(callers);
        Files.writeString(out.resolve("callers.tsv"), edges, StandardCharsets.UTF_8);
        DecompInterface decompiler = new DecompInterface();
        if (!decompiler.openProgram(currentProgram)) throw new IllegalStateException(decompiler.getLastMessage());
        StringBuilder index = new StringBuilder("entry\tname\tstatus\n");
        try {
            for (Function function : functions.values()) {
                monitor.checkCancelled();
                DecompileResults result = decompiler.decompileFunction(function, 30, monitor);
                String entry = function.getEntryPoint().toString();
                boolean completed = result.decompileCompleted();
                index.append(entry).append('\t').append(function.getName()).append('\t')
                    .append(completed ? "completed" : result.getErrorMessage()).append('\n');
                if (completed) Files.writeString(out.resolve(entry + ".c"),
                    "/* Inferred decompilation; verify against original ARM instructions. */\n" +
                    result.getDecompiledFunction().getC(), StandardCharsets.UTF_8);
            }
        } finally { decompiler.dispose(); }
        Files.writeString(out.resolve("index.tsv"), index, StandardCharsets.UTF_8);
        println("Exported " + functions.size() + " selected stock functions to " + out);
    }
}

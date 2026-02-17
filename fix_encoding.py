"""Fix last 3 remaining mojibake patterns."""
import pathlib

p = pathlib.Path(r'c:\Startup\GenAISample\RAG_HR_ASSISTANT\frontend\src\pages\LandingPage.js')
b = p.read_bytes()

# Show exact bytes for the 3 remaining issues
lines = b.split(b'\n')
for ln in [588, 762, 648, 944]:
    if ln <= len(lines):
        line = lines[ln - 1]
        # Find non-ASCII range
        for i, byte in enumerate(line):
            if byte > 127:
                end = min(i + 30, len(line))
                print(f'Line {ln}: offset {i}, hex: {line[i:end].hex(" ")}')
                print(f'  context: ...{line[max(0,i-10):end].decode("utf-8", errors="replace")}...')
                break

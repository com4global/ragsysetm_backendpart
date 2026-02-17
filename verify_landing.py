"""Verify the generated LandingPage.js is structurally sound."""
import pathlib

SRC = pathlib.Path(r"c:\Startup\GenAISample\RAG_HR_ASSISTANT\frontend\src\pages\LandingPage.js")
text = SRC.read_text(encoding='utf-8')

# Check tag balance
tags = ['nav', 'section', 'div', 'button', 'footer']
for t in tags:
    opens = text.count('<' + t + ' ') + text.count('<' + t + '>')
    closes = text.count('</' + t + '>')
    status = 'OK' if opens == closes else 'MISMATCH'
    print('  {}: {} open, {} close [{}]'.format(t, opens, closes, status))

# Check no mojibake
safe = set('\u00d7\u00a9\u2192\u2714\u2728\U0001F3AF\U0001F680\U0001F9E0\U0001F4BC\U0001F4CA\U0001F517')
bad = 0
for i, line in enumerate(text.split('\n'), 1):
    for ch in line:
        if ord(ch) > 127 and ch not in safe:
            bad += 1
            if bad <= 3:
                print('  BAD: Line {} U+{:04X}'.format(i, ord(ch)))
            break

print('\nMojibake lines: {}'.format(bad))
print('Total lines: {}'.format(len(text.splitlines())))
print('Has export default: {}'.format('export default' in text))
print('Has return: {}'.format('return (' in text))
print('Ends with }}: {}'.format(text.rstrip().endswith('}')))

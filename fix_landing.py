"""Fix structural damage in LandingPage.js by inserting missing sections."""
import pathlib

SRC = pathlib.Path(r"c:\Startup\GenAISample\RAG_HR_ASSISTANT\frontend\src\pages\LandingPage.js")
text = SRC.read_text(encoding='utf-8')

# Fix double \r\r\n -> \r\n
text = text.replace('\r\r\n', '\r\n')
text = text.replace('\r\n', '\n')

# The broken section: handleStartTrial() directly followed by onClick for Watch Demo
# We need to insert: button close, style, nav close, and entire Hero section

BROKEN = """                handleStartTrial();
              }}
                //handleStartTrial
                alignItems: 'center',"""

# Check if the broken section exists
if BROKEN not in text:
    # Try alternate broken patterns
    # Let's find where handleStartTrial is and see what follows
    idx = text.find('handleStartTrial();')
    if idx == -1:
        print("ERROR: Cannot find handleStartTrial() in file")
        exit(1)
    # Show context
    snippet = text[idx:idx+300]
    print(f"Found at offset {idx}. Context:")
    print(repr(snippet[:300]))
    print()

# Let's find the exact break point more flexibly
lines = text.split('\n')
handle_line = None
for i, line in enumerate(lines):
    if 'handleStartTrial();' in line:
        handle_line = i
        break

if handle_line is None:
    print("ERROR: handleStartTrial() not found")
    exit(1)

print(f"handleStartTrial() at line {handle_line+1}")
print(f"Context lines {handle_line+1} to {handle_line+20}:")
for j in range(handle_line, min(handle_line+20, len(lines))):
    print(f"  {j+1}: {lines[j].rstrip()}")

# Find the Watch Demo button onClick
watch_demo_line = None
for i in range(handle_line, min(handle_line+30, len(lines))):
    if 'setShowDemoModal(true)' in lines[i]:
        watch_demo_line = i
        break

if watch_demo_line:
    print(f"\nWatch Demo onClick at line {watch_demo_line+1}")

# The missing content that should go between handleStartTrial() and the Watch Demo button
MISSING_SECTION = """              style={{ background: 'linear-gradient(135deg, #667eea, #764ba2)', border: 'none', padding: '0.6rem 1.5rem', borderRadius: '8px', color: '#fff', cursor: 'pointer', fontWeight: 600, boxShadow: '0 4px 15px rgba(102, 126, 234, 0.4)' }}
            >
              Start Free {\"\\u2192\"}
            </button>
          </div>
        </div>
      </nav>

      {/* Hero Section */}
      <section style={{
        minHeight: '100vh',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        background: 'radial-gradient(circle at 50% 0%, rgba(102, 126, 234, 0.15), transparent 50%), radial-gradient(circle at 0% 100%, rgba(118, 75, 162, 0.15), transparent 50%)',
        position: 'relative',
        padding: '8rem 2rem 4rem'
      }}>
        <div style={{ maxWidth: '1400px', width: '100%', textAlign: 'center', position: 'relative', zIndex: 1 }}>

          {/* Animated Badge */}
          <div style={{
            display: 'inline-flex',
            alignItems: 'center',
            gap: '0.5rem',
            background: 'rgba(102, 126, 234, 0.1)',
            border: '1px solid rgba(102, 126, 234, 0.3)',
            padding: '0.5rem 1.25rem',
            borderRadius: '50px',
            marginBottom: '2rem',
            animation: 'fadeInDown 0.8s ease'
          }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#667eea' }}>{\"\\u2728\"} NEW</span>
            <span style={{ fontSize: '0.85rem', color: '#d1d5db' }}>Claude Sonnet 4 Now Available</span>
          </div>

          <h1 style={{
            fontSize: 'clamp(2.5rem, 6vw, 5rem)',
            fontWeight: 900,
            lineHeight: 1.1,
            marginBottom: '1.5rem',
            background: 'linear-gradient(135deg, #fff 0%, #d1d5db 100%)',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            animation: 'fadeInUp 1s ease'
          }}>
            Your Enterprise<br/>
            <span style={{ background: 'linear-gradient(135deg, #667eea, #764ba2)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
              Knowledge Assistant
            </span>
          </h1>

          <p style={{
            fontSize: '1.35rem',
            color: '#9ca3af',
            maxWidth: '700px',
            margin: '0 auto 3rem',
            lineHeight: 1.6,
            animation: 'fadeInUp 1.2s ease'
          }}>
            Process any document, video, or audio file. Get instant AI-powered answers from your data with GPT-4, Claude, or Gemini.
          </p>

          {/* CTA Buttons */}
          <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', flexWrap: 'wrap', marginBottom: '4rem', animation: 'fadeInUp 1.4s ease' }}>
            <button
              onClick={() => {
                if (isAuthenticated) {
                  navigate('/chat');
                } else {
                  navigate('/login');
                }
              }}
              style={{
                background: 'linear-gradient(135deg, #667eea, #764ba2)',
                border: 'none',
                padding: '1rem 2.5rem',
                borderRadius: '12px',
                color: '#fff',
                fontSize: '1.1rem',
                fontWeight: 700,
                cursor: 'pointer',
                boxShadow: '0 10px 30px rgba(102, 126, 234, 0.4)',
                transition: 'transform 0.2s',
                display: 'flex',
                alignItems: 'center',
                gap: '0.5rem'
              }}
            >
              Start Free Trial <span style={{ fontSize: '1.2rem' }}>{\"\\u2192\"}</span>
            </button>"""

# Now find the exact lines to replace
# We need to replace from the line after handleStartTrial() up to the line before setShowDemoModal
# First, find the }} that closes handleStartTrial's onClick
close_line = handle_line + 1
while close_line < len(lines) and '}}' not in lines[close_line]:
    close_line += 1

# Find all the garbage between handleStartTrial and Watch Demo onClick
# We want to replace from close_line to just before the <button with Watch Demo
replace_start = close_line + 1
replace_end = watch_demo_line

if watch_demo_line:
    # Find the <button tag that contains the Watch Demo onClick
    # Go backwards from setShowDemoModal to find the <button
    button_line = watch_demo_line
    for j in range(watch_demo_line, max(watch_demo_line - 10, handle_line), -1):
        if '<button' in lines[j] or 'onClick' in lines[j]:
            button_line = j
            break

    print(f"\nReplacing lines {replace_start+1} to {button_line} with missing section")

    # Build the new content
    new_lines = lines[:handle_line+1]  # Keep everything up to and including handleStartTrial()
    new_lines.append('              }}')
    new_lines.append(MISSING_SECTION)
    new_lines.append('            <button')
    new_lines.append('              onClick={() => {')
    new_lines.append('                setShowDemoModal(true);')
    new_lines.append('                setIsVideoPlaying(true);')
    new_lines.append('                setCurrentVideoIndex(0);')
    new_lines.append('              }}')

    # Skip forward to find where the Watch Demo button style starts
    style_start = watch_demo_line + 1
    for j in range(watch_demo_line + 1, min(watch_demo_line + 20, len(lines))):
        if 'style={{' in lines[j] or 'style =' in lines[j]:
            style_start = j
            break

    # Add the rest of the file from the Watch Demo button style onwards
    new_lines.extend(lines[style_start:])

    result = '\n'.join(new_lines)
    SRC.write_text(result, encoding='utf-8')

    new_line_count = len(result.split('\n'))
    print(f"\nFile written: {new_line_count} lines")

    # Verify tag balance
    print(f"nav: {result.count('<nav')} open, {result.count('</nav>')} close")
    print(f"section: {result.count('<section')} open, {result.count('</section')} close")
else:
    print("ERROR: Could not find Watch Demo onClick")

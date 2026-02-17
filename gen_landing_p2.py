"""Generate clean LandingPage.js - Part 2: Hero through Footer. Uses regular strings, not f-strings."""
import pathlib

DST = pathlib.Path(r"c:\Startup\GenAISample\RAG_HR_ASSISTANT\frontend\src\pages\LandingPage.js")

# The JSX content uses PLACEHOLDERS that we replace at the end
content = r'''
      {/* Hero Section */}
      <section style={{ minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'radial-gradient(circle at 50% 0%, rgba(102, 126, 234, 0.15), transparent 50%), radial-gradient(circle at 0% 100%, rgba(118, 75, 162, 0.15), transparent 50%)', position: 'relative', padding: '8rem 2rem 4rem' }}>
        <div style={{ maxWidth: '1400px', width: '100%', textAlign: 'center', position: 'relative', zIndex: 1 }}>
          <div style={{ display: 'inline-flex', alignItems: 'center', gap: '0.5rem', background: 'rgba(102, 126, 234, 0.1)', border: '1px solid rgba(102, 126, 234, 0.3)', padding: '0.5rem 1.25rem', borderRadius: '50px', marginBottom: '2rem', animation: 'fadeInDown 0.8s ease' }}>
            <span style={{ fontSize: '0.85rem', fontWeight: 600, color: '#667eea' }}>__SPARK__ NEW</span>
            <span style={{ fontSize: '0.85rem', color: '#d1d5db' }}>Claude Sonnet 4 Now Available</span>
          </div>
          <h1 style={{ fontSize: 'clamp(2.5rem, 6vw, 5rem)', fontWeight: 900, lineHeight: 1.1, marginBottom: '1.5rem', background: 'linear-gradient(135deg, #fff 0%, #d1d5db 100%)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent', animation: 'fadeInUp 1s ease' }}>
            Your Enterprise<br/>
            <span style={{ background: 'linear-gradient(135deg, #667eea, #764ba2)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>Knowledge Assistant</span>
          </h1>
          <p style={{ fontSize: '1.35rem', color: '#9ca3af', maxWidth: '700px', margin: '0 auto 3rem', lineHeight: 1.6, animation: 'fadeInUp 1.2s ease' }}>
            Process any document, video, or audio file. Get instant AI-powered answers from your data with GPT-4, Claude, or Gemini.
          </p>
          <div style={{ display: 'flex', gap: '1rem', justifyContent: 'center', flexWrap: 'wrap', marginBottom: '4rem', animation: 'fadeInUp 1.4s ease' }}>
            <button onClick={() => { if (isAuthenticated) { navigate('/chat'); } else { navigate('/login'); } }} style={{ background: 'linear-gradient(135deg, #667eea, #764ba2)', border: 'none', padding: '1rem 2.5rem', borderRadius: '12px', color: '#fff', fontSize: '1.1rem', fontWeight: 700, cursor: 'pointer', boxShadow: '0 10px 30px rgba(102, 126, 234, 0.4)', transition: 'transform 0.2s', display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
              Start Free Trial <span style={{ fontSize: '1.2rem' }}>__ARROW__</span>
            </button>
            <button onClick={() => { setShowDemoModal(true); setIsVideoPlaying(true); setCurrentVideoIndex(0); }} style={{ background: 'rgba(255, 255, 255, 0.08)', backdropFilter: 'blur(10px)', border: '1px solid rgba(255, 255, 255, 0.2)', padding: '1rem 2.5rem', borderRadius: '12px', color: '#fff', fontSize: '1.1rem', fontWeight: 600, cursor: 'pointer', transition: 'all 0.3s ease', display: 'flex', alignItems: 'center', gap: '0.8rem' }}>
              <span style={{ width: '24px', height: '24px', borderRadius: '50%', background: 'linear-gradient(135deg, #667eea, #764ba2)', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.7rem' }}>&#9654;</span> Watch Demo
            </button>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '2rem', maxWidth: '800px', margin: '0 auto', animation: 'fadeInUp 1.6s ease' }}>
            {stats.map((stat, idx) => (
              <div key={idx} style={{ textAlign: 'center' }}>
                <div style={{ fontSize: '2rem', fontWeight: 800, background: 'linear-gradient(135deg, #667eea, #764ba2)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>{stat.value}</div>
                <div style={{ fontSize: '0.85rem', color: '#9ca3af', marginTop: '0.25rem' }}>{stat.label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Model Selection */}
      <section id="models" style={{ padding: '6rem 2rem', background: '#0a0a0a' }}>
        <div style={{ maxWidth: '1400px', margin: '0 auto' }}>
          <h2 style={{ fontSize: '2.5rem', fontWeight: 800, textAlign: 'center', marginBottom: '1rem', background: 'linear-gradient(135deg, #fff, #d1d5db)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>Choose Your AI Model</h2>
          <p style={{ textAlign: 'center', color: '#9ca3af', marginBottom: '3rem', fontSize: '1.1rem' }}>Select the best model for your needs</p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(280px, 1fr))', gap: '1.5rem' }}>
            {models.map((model) => (
              <div key={model.id} onClick={() => setSelectedModel(model.id)} style={{ background: selectedModel === model.id ? 'rgba(102, 126, 234, 0.15)' : 'rgba(255, 255, 255, 0.03)', border: selectedModel === model.id ? '2px solid #667eea' : '1px solid rgba(255, 255, 255, 0.1)', borderRadius: '16px', padding: '2rem', cursor: 'pointer', transition: 'all 0.3s ease', position: 'relative' }}>
                {model.popular && <div style={{ position: 'absolute', top: '-10px', right: '20px', background: 'linear-gradient(135deg, #667eea, #764ba2)', padding: '0.25rem 1rem', borderRadius: '50px', fontSize: '0.75rem', fontWeight: 700 }}>POPULAR</div>}
                <div style={{ width: '12px', height: '12px', borderRadius: '50%', background: model.color, marginBottom: '1rem' }}></div>
                <h3 style={{ fontSize: '1.25rem', fontWeight: 700, marginBottom: '0.5rem' }}>{model.name}</h3>
                <p style={{ color: '#667eea', fontWeight: 600, fontSize: '1.1rem', marginBottom: '0.5rem' }}>{model.price}</p>
                <p style={{ color: '#9ca3af', fontSize: '0.9rem', marginBottom: '1rem' }}>Speed: {model.speed}</p>
                {model.features.map((feature, idx) => (
                  <div key={idx} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.5rem' }}>
                    <span style={{ color: '#667eea' }}>__CHECK__</span> <span style={{ color: '#d1d5db', fontSize: '0.9rem' }}>{feature}</span>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Features */}
      <section id="features" style={{ padding: '6rem 2rem', background: 'linear-gradient(180deg, #0a0a0a 0%, #111 100%)' }}>
        <div style={{ maxWidth: '1400px', margin: '0 auto' }}>
          <h2 style={{ fontSize: '2.5rem', fontWeight: 800, textAlign: 'center', marginBottom: '1rem', background: 'linear-gradient(135deg, #fff, #d1d5db)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>Powerful Features</h2>
          <p style={{ textAlign: 'center', color: '#9ca3af', marginBottom: '3rem', fontSize: '1.1rem' }}>Everything you need for enterprise AI</p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: '1.5rem' }}>
            {features.map((feature, idx) => (
              <div key={idx} style={{ background: currentFeature === idx ? 'rgba(102, 126, 234, 0.1)' : 'rgba(255, 255, 255, 0.03)', border: currentFeature === idx ? '1px solid rgba(102, 126, 234, 0.5)' : '1px solid rgba(255, 255, 255, 0.08)', borderRadius: '16px', padding: '2rem', transition: 'all 0.5s ease' }}>
                <div style={{ fontSize: '2rem', marginBottom: '1rem' }}>{feature.icon}</div>
                <h3 style={{ fontSize: '1.2rem', fontWeight: 700, marginBottom: '0.5rem' }}>{feature.title}</h3>
                <p style={{ color: '#9ca3af', marginBottom: '1rem', lineHeight: 1.6 }}>{feature.description}</p>
                <span style={{ color: '#667eea', fontSize: '0.85rem', fontWeight: 600 }}>{feature.demo}</span>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Pricing */}
      <section id="pricing" style={{ padding: '6rem 2rem', background: '#0a0a0a' }}>
        <div style={{ maxWidth: '1200px', margin: '0 auto' }}>
          <h2 style={{ fontSize: '2.5rem', fontWeight: 800, textAlign: 'center', marginBottom: '1rem', background: 'linear-gradient(135deg, #fff, #d1d5db)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>Simple Pricing</h2>
          <p style={{ textAlign: 'center', color: '#9ca3af', marginBottom: '3rem', fontSize: '1.1rem' }}>Start free. Scale as you grow.</p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '1.5rem', alignItems: 'start' }}>
            {pricingPlans.map((plan, idx) => (
              <div key={idx} onMouseEnter={() => setHoveredPricing(idx)} onMouseLeave={() => setHoveredPricing(null)} style={{ background: plan.popular ? 'linear-gradient(135deg, rgba(102, 126, 234, 0.15), rgba(118, 75, 162, 0.15))' : 'rgba(255, 255, 255, 0.03)', border: plan.popular ? '2px solid #667eea' : '1px solid rgba(255, 255, 255, 0.1)', borderRadius: '20px', padding: '2.5rem', transition: 'all 0.3s ease', transform: hoveredPricing === idx ? 'translateY(-5px)' : 'none', position: 'relative' }}>
                {plan.popular && <div style={{ position: 'absolute', top: '-12px', left: '50%', transform: 'translateX(-50%)', background: 'linear-gradient(135deg, #667eea, #764ba2)', padding: '0.3rem 1.5rem', borderRadius: '50px', fontSize: '0.8rem', fontWeight: 700 }}>MOST POPULAR</div>}
                <h3 style={{ fontSize: '1.5rem', fontWeight: 700, marginBottom: '0.5rem' }}>{plan.name}</h3>
                <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.25rem', marginBottom: '0.5rem' }}>
                  <span style={{ fontSize: '3rem', fontWeight: 800, background: 'linear-gradient(135deg, #667eea, #764ba2)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>{plan.price}</span>
                  <span style={{ color: '#9ca3af' }}>{plan.period}</span>
                </div>
                <p style={{ color: '#9ca3af', marginBottom: '1.5rem' }}>{plan.description}</p>
                {plan.features.map((feature, fIdx) => (
                  <div key={fIdx} style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', marginBottom: '0.75rem' }}>
                    <span style={{ color: '#667eea' }}>__CHECK__</span> <span style={{ color: '#d1d5db' }}>{feature}</span>
                  </div>
                ))}
                <button onClick={handleStartTrial} style={{ width: '100%', marginTop: '1.5rem', padding: '0.875rem', borderRadius: '12px', border: plan.popular ? 'none' : '1px solid rgba(255, 255, 255, 0.2)', background: plan.popular ? 'linear-gradient(135deg, #667eea, #764ba2)' : 'transparent', color: '#fff', fontSize: '1rem', fontWeight: 600, cursor: 'pointer', transition: 'all 0.3s ease' }}>{plan.cta}</button>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Demo Video Modal */}
      {showDemoModal && (
        <div style={{ position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.9)', zIndex: 2000, display: 'flex', alignItems: 'center', justifyContent: 'center', padding: '2rem' }} onClick={() => { setShowDemoModal(false); setIsVideoPlaying(false); }}>
          <div style={{ maxWidth: '900px', width: '100%', position: 'relative' }} onClick={(e) => e.stopPropagation()}>
            <button onClick={() => { setShowDemoModal(false); setIsVideoPlaying(false); }} style={{ position: 'absolute', top: '-40px', right: 0, background: 'none', border: 'none', color: '#fff', fontSize: '2rem', cursor: 'pointer' }}>__TIMES__</button>
            <video ref={videoRef} controls autoPlay style={{ width: '100%', borderRadius: '12px' }} />
            <div style={{ display: 'flex', gap: '0.5rem', marginTop: '1rem', justifyContent: 'center' }}>
              {DEMO_VIDEOS.map((video, idx) => (
                <button key={video.id} onClick={() => { setCurrentVideoIndex(idx); setIsVideoPlaying(true); }} style={{ padding: '0.5rem 1rem', borderRadius: '8px', border: currentVideoIndex === idx ? '1px solid #667eea' : '1px solid rgba(255,255,255,0.2)', background: currentVideoIndex === idx ? 'rgba(102,126,234,0.2)' : 'transparent', color: '#fff', cursor: 'pointer', fontSize: '0.85rem' }}>{video.title}</button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Footer */}
      <footer style={{ padding: '3rem 2rem', borderTop: '1px solid rgba(255, 255, 255, 0.1)', textAlign: 'center' }}>
        <p style={{ color: '#6b7280', fontSize: '0.9rem' }}>__COPY__ 2024 RAG.AI. All rights reserved.</p>
      </footer>

      <style>{`
        @keyframes fadeInUp { from { opacity: 0; transform: translateY(20px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes fadeInDown { from { opacity: 0; transform: translateY(-20px); } to { opacity: 1; transform: translateY(0); } }
        @keyframes float { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-10px); } }
        button:hover { transform: translateY(-2px); }
        a:hover { color: #667eea !important; }
      `}</style>
    </div>
  );
}
'''

# Replace placeholders with actual Unicode characters
content = content.replace('__ARROW__', '\u2192')
content = content.replace('__SPARK__', '\u2728')
content = content.replace('__CHECK__', '\u2714')
content = content.replace('__TIMES__', '\u00D7')
content = content.replace('__COPY__', '\u00A9')

# Read Part 1 and append Part 2
existing = DST.read_text(encoding='utf-8')
result = existing + content
DST.write_text(result, encoding='utf-8')

total_lines = result.count('\n') + 1
print(f"Complete! Total: {total_lines} lines, {len(result)} chars")
print(f"nav: {result.count('<nav')} open, {result.count('</nav>')} close")
print(f"section: {result.count('<section')} open, {result.count('</section>')} close")

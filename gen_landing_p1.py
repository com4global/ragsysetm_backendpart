"""Generate clean LandingPage.js - Part 1: Write first half"""
import pathlib

DST = pathlib.Path(r"c:\Startup\GenAISample\RAG_HR_ASSISTANT\frontend\src\pages\LandingPage.js")

# Unicode constants
ROCKET = '\U0001F680'
TARGET = '\U0001F3AF'
BRAIN = '\U0001F9E0'
BRIEF = '\U0001F4BC'
CHART = '\U0001F4CA'
LINK = '\U0001F517'
ARROW = '\u2192'
SPARK = '\u2728'
CHECK = '\u2714'
TIMES = '\u00D7'
COPY = '\u00A9'

content = f'''import {{ useNavigate }} from 'react-router-dom';
import React, {{ useState, useEffect, useRef }} from 'react';
import {{ useAuth }} from '../contexts/AuthContext';
import '../Styles/AdminDashboard.css';

const DEMO_VIDEOS = [
  {{ id: 1, title: 'Platform Overview', url: '/advertiseA.mp4' }},
  {{ id: 2, title: 'AI Features', url: '/advertiseb.mp4' }},
  {{ id: 3, title: 'Enterprise Workflow', url: '/advertisec.mp4' }}
];

export default function LandingPage() {{
  const [isScrolled, setIsScrolled] = useState(false);
  const [selectedModel, setSelectedModel] = useState(null);
  const [currentFeature, setCurrentFeature] = useState(0);
  const [hoveredPricing, setHoveredPricing] = useState(null);
  const navigate = useNavigate();
  const {{ isAuthenticated }} = useAuth();

  const handleStartTrial = () => {{
    if (isAuthenticated) {{ navigate('/chat'); }} else {{ navigate('/login'); }}
  }};

  useEffect(() => {{
    const handleScroll = () => setIsScrolled(window.scrollY > 50);
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }}, []);

  const [currentVideoIndex, setCurrentVideoIndex] = useState(0);
  const [isVideoPlaying, setIsVideoPlaying] = useState(false);
  const [showDemoModal, setShowDemoModal] = useState(false);
  const videoRef = useRef(null);

  useEffect(() => {{
    const videoElement = videoRef.current;
    if (!videoElement) return;
    const handleVideoEnd = () => {{ setCurrentVideoIndex((prev) => (prev + 1) % DEMO_VIDEOS.length); }};
    videoElement.addEventListener('ended', handleVideoEnd);
    return () => videoElement.removeEventListener('ended', handleVideoEnd);
  }}, []);

  useEffect(() => {{
    const videoElement = videoRef.current;
    if (videoElement && showDemoModal) {{
      videoElement.src = DEMO_VIDEOS[currentVideoIndex].url;
      videoElement.load();
      if (isVideoPlaying) {{ videoElement.play().catch(err => console.warn('Autoplay blocked', err)); }}
    }}
  }}, [currentVideoIndex, isVideoPlaying, showDemoModal]);

  useEffect(() => {{
    const handleEsc = (e) => {{ if (e.key === 'Escape' && showDemoModal) {{ setShowDemoModal(false); setIsVideoPlaying(false); }} }};
    window.addEventListener('keydown', handleEsc);
    return () => window.removeEventListener('keydown', handleEsc);
  }}, [showDemoModal]);

  const models = [
    {{ id: 'gpt-3', name: 'GPT-3.5 Turbo', price: '$0.002/1K tokens', speed: 'Fast', features: ['Basic reasoning', 'Quick responses', 'Cost-effective', 'Standard accuracy'], color: '#10b981' }},
    {{ id: 'gpt-4', name: 'GPT-4 Turbo', price: '$0.01/1K tokens', speed: 'Moderate', features: ['Advanced reasoning', 'Higher accuracy', 'Complex tasks', '128K context'], color: '#3b82f6', popular: true }},
    {{ id: 'claude', name: 'Claude Sonnet 4', price: '$0.015/1K tokens', speed: 'Fast', features: ['Superior reasoning', 'Longest context', 'Best for research', '200K tokens'], color: '#8b5cf6' }},
    {{ id: 'gemini', name: 'Gemini Pro', price: '$0.00125/1K tokens', speed: 'Very Fast', features: ['Multimodal AI', 'Image & video', 'Lowest cost', 'Google integration'], color: '#f59e0b' }}
  ];

  const features = [
    {{ icon: '{TARGET}', title: 'Multi-Source RAG', description: 'Upload PDFs, videos, audio, images, YouTube links - we handle it all', demo: 'Process 100+ file types instantly' }},
    {{ icon: '{ROCKET}', title: 'Lightning Fast Search', description: 'Get answers in milliseconds with advanced vector search', demo: 'Query 1M+ documents in <200ms' }},
    {{ icon: '{BRAIN}', title: 'Smart Model Selection', description: 'Choose GPT-4, Claude, or Gemini based on your needs', demo: 'Auto-route to best model' }},
    {{ icon: '{BRIEF}', title: 'Enterprise Security', description: 'SOC 2, GDPR compliant with end-to-end encryption', demo: 'Bank-level encryption' }},
    {{ icon: '{CHART}', title: 'Analytics Dashboard', description: 'Track usage, costs, and performance in real-time', demo: 'Live insights & reporting' }},
    {{ icon: '{LINK}', title: 'Seamless Integration', description: 'REST API, webhooks, and SDKs for easy integration', demo: 'Deploy in 5 minutes' }}
  ];

  const pricingPlans = [
    {{ name: 'Starter', price: '$29', period: '/month', description: 'Perfect for individuals', features: ['10K tokens/month', 'All AI models', '100 documents', 'Email support', 'Basic analytics'], cta: 'Start Free Trial', popular: false }},
    {{ name: 'Professional', price: '$99', period: '/month', description: 'For growing teams', features: ['100K tokens/month', 'All AI models', 'Unlimited documents', 'Priority support', 'Advanced analytics', 'API access', 'Custom integrations'], cta: 'Start Free Trial', popular: true }},
    {{ name: 'Enterprise', price: 'Custom', period: '', description: 'For large organizations', features: ['Unlimited tokens', 'All AI models', 'Unlimited documents', '24/7 dedicated support', 'Custom AI training', 'SLA guarantee', 'On-premise deployment', 'White-label solution'], cta: 'Contact Sales', popular: false }}
  ];

  const stats = [
    {{ value: '10M+', label: 'Documents Processed' }},
    {{ value: '99.9%', label: 'Uptime SLA' }},
    {{ value: '< 200ms', label: 'Average Response' }},
    {{ value: '50K+', label: 'Happy Users' }}
  ];

  useEffect(() => {{
    const interval = setInterval(() => {{ setCurrentFeature((prev) => (prev + 1) % features.length); }}, 4000);
    return () => clearInterval(interval);
  }}, [features.length]);

  return (
    <div style={{{{ fontFamily: 'system-ui, -apple-system, sans-serif', background: '#0a0a0a', color: '#fff', overflow: 'hidden' }}}}>
      {{/* Navigation */}}
      <nav style={{{{
        position: 'fixed', top: 0, left: 0, right: 0, zIndex: 1000,
        background: isScrolled ? 'rgba(10, 10, 10, 0.95)' : 'transparent',
        backdropFilter: isScrolled ? 'blur(10px)' : 'none',
        borderBottom: isScrolled ? '1px solid rgba(255, 255, 255, 0.1)' : 'none',
        transition: 'all 0.3s ease', padding: '1.25rem 2rem'
      }}}}>
        <div style={{{{ maxWidth: '1400px', margin: '0 auto', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}}}>
          <div style={{{{ display: 'flex', alignItems: 'center', gap: '1rem' }}}}>
            <div style={{{{ width: '45px', height: '45px', background: 'linear-gradient(135deg, #667eea, #764ba2)', borderRadius: '12px', display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '1.5rem', fontWeight: 'bold', boxShadow: '0 4px 20px rgba(102, 126, 234, 0.4)' }}}}>
              {ROCKET}
            </div>
            <span style={{{{ fontSize: '1.5rem', fontWeight: 800, background: 'linear-gradient(135deg, #667eea, #764ba2)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}}}>RAG.AI</span>
          </div>
          <div style={{{{ display: 'flex', gap: '2.5rem', alignItems: 'center' }}}}>
            <a href="#features" style={{{{ color: '#d1d5db', textDecoration: 'none', fontWeight: 500 }}}}>Features</a>
            <a href="#pricing" style={{{{ color: '#d1d5db', textDecoration: 'none', fontWeight: 500 }}}}>Pricing</a>
            <a href="#docs" style={{{{ color: '#d1d5db', textDecoration: 'none', fontWeight: 500 }}}}>Docs</a>
            <button onClick={{() => {{ if (isAuthenticated) {{ navigate('/chat'); }} else {{ navigate('/login'); }} }}}} style={{{{ background: 'none', border: '1px solid rgba(255, 255, 255, 0.2)', padding: '0.6rem 1.5rem', borderRadius: '8px', color: '#fff', cursor: 'pointer', fontWeight: 600 }}}}>Sign In</button>
            <button onClick={{handleStartTrial}} style={{{{ background: 'linear-gradient(135deg, #667eea, #764ba2)', border: 'none', padding: '0.6rem 1.5rem', borderRadius: '8px', color: '#fff', cursor: 'pointer', fontWeight: 600, boxShadow: '0 4px 15px rgba(102, 126, 234, 0.4)' }}}}>Start Free {ARROW}</button>
          </div>
        </div>
      </nav>
'''

# Write Part 1
DST.write_text(content, encoding='utf-8')
print(f"Part 1 written: {len(content)} chars, {content.count(chr(10))} lines")

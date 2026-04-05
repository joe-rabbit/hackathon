import './App.css';
import { useState, useEffect, useRef, useCallback } from 'react';

// ═══════════════════════════════════════════════════════════════════════════════
// CONSTANTS & MOCK DATA
// ═══════════════════════════════════════════════════════════════════════════════

const DASHBOARD_URL = "http://localhost:8501";
const RAINBOW_COLORS = ["#ff0000", "#ff8700", "#ffff00", "#00ff00", "#0087ff", "#5f00ff", "#af00ff"];
const SPARKLE_CHARS = ["✦", "✧", "★", "☆", "·", "✸", "✺", "⋆", "*"];

const MOCK_AGENTS = [
  { name: "Camera Vision", cpu: 85, mem: 380, tok: 1997, status: "HOT", latency: 540, temp: 61.7, optimizer: "compressing" },
  { name: "NLP Process", cpu: 39, mem: 280, tok: 677, status: "OK", latency: 210, temp: 45.2, optimizer: "none" },
  { name: "Object Detect", cpu: 38, mem: 172, tok: 523, status: "OK", latency: 180, temp: 44.8, optimizer: "batched" },
  { name: "Request Router", cpu: 19, mem: 77, tok: 220, status: "OK", latency: 50, temp: 38.1, optimizer: "none" },
  { name: "Audio Process", cpu: 49, mem: 231, tok: 592, status: "OK", latency: 260, temp: 48.3, optimizer: "none" },
];

const MOCK_ALERTS = [
  "camera-agent token spike detected",
  "camera-agent CPU above hot threshold",
];

// ═══════════════════════════════════════════════════════════════════════════════
// MOCHI CAT SPRITE - Pixel art style (exactly like the Python version)
// ═══════════════════════════════════════════════════════════════════════════════

function getMochiRows(mood, blinking, frame) {
  let leftEye = 'D', rightEye = 'd', mouth = 'M';

  if (blinking) {
    leftEye = 'L'; rightEye = 'l';
  } else if (mood === 'happy' || mood === 'celebrate') {
    if (mood === 'celebrate' && Math.floor(frame / 8) % 2 === 0) {
      leftEye = 'S'; rightEye = 's';
    } else {
      leftEye = 'H'; rightEye = 'h';
    }
    mouth = 'G';
  } else if (mood === 'warning') {
    leftEye = 'W'; rightEye = 'w'; mouth = 'F';
  } else if (mood === 'sad') {
    leftEye = 'W'; rightEye = 'w'; mouth = 'S';
  } else if (mood === 'thinking') {
    leftEye = 'T'; rightEye = 't';
  } else if (mood === 'sleepy') {
    leftEye = 'L'; rightEye = 'l'; mouth = 'Z';
  }

  return [
    '..BBBBB..',
    '.BBBBBBB.',
    'BPBBBBBBB',
    'BBBCB' + leftEye + 'B' + rightEye + 'B',
    '..BB.' + mouth + mouth + '..',
    '.ABBBBBA.',
    '..AA..AA.',
  ];
}

// Cat sprite component with pixel-art styling
function MochiSprite({ mood, blinking, frame }) {
  const rows = getMochiRows(mood, blinking, frame);

  const cellColors = {
    '.': 'transparent',
    'B': '#d7d787',  // warm yellow body
    'P': '#ffffff',  // white shine
    'C': '#ff87d7',  // pink cheek
    'A': '#ffff87',  // arm yellow
    'M': '#ff8787',  // mouth pink
    'F': '#555555',  // flat/worried mouth
    'S': '#888888',  // sad mouth
    'G': '#ffffff',  // grin white
    'Z': '#87d7ff',  // sleepy z mouth
  };

  const eyeChars = {
    'D': { char: ' O', fg: '#303030' },
    'd': { char: 'O ', fg: '#303030' },
    'L': { char: '──', fg: '#8b4513' },
    'l': { char: '──', fg: '#8b4513' },
    'H': { char: ' ^', fg: '#303030' },
    'h': { char: '^ ', fg: '#303030' },
    'W': { char: ' >', fg: '#303030' },
    'w': { char: '< ', fg: '#303030' },
    'T': { char: ' ?', fg: '#303030' },
    't': { char: '? ', fg: '#303030' },
    'S': { char: ' ~', fg: '#303030' },
    's': { char: '~ ', fg: '#303030' },
    'X': { char: ' X', fg: '#ff5f5f' },
    'x': { char: 'X ', fg: '#ff5f5f' },
  };

  return (
    <div className="mochi-sprite">
      {rows.map((row, rowIdx) => (
        <div key={rowIdx} className="mochi-row">
          {row.split('').map((cell, cellIdx) => {
            if (eyeChars[cell]) {
              const { char, fg } = eyeChars[cell];
              return (
                <span key={cellIdx} className="mochi-cell eye" style={{ backgroundColor: '#d7d787', color: fg }}>
                  {char}
                </span>
              );
            }
            return (
              <span
                key={cellIdx}
                className="mochi-cell"
                style={{ backgroundColor: cellColors[cell] || 'transparent' }}
              >
                {'  '}
              </span>
            );
          })}
        </div>
      ))}
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// HERO SECTION WITH NYAN-STYLE ANIMATION
// ═══════════════════════════════════════════════════════════════════════════════

function MochiHero({ frame, mood, mochiX, mochiY, mochiDirection, sparkles, rainbowOffset, heroWidth, blinking }) {
  const trailLen = Math.min(heroWidth * 0.35, 280);

  return (
    <div className="hero-nyan">
      {/* Sparkles */}
      <div className="sparkles-container">
        {sparkles.map((sp, idx) => {
          const opacity = sp.age < sp.maxAge / 2 ? 1 : 1 - (sp.age - sp.maxAge / 2) / (sp.maxAge / 2);
          if (opacity <= 0) return null;
          return (
            <span
              key={idx}
              className="sparkle"
              style={{
                left: sp.x + 'px',
                top: sp.y + 'px',
                opacity,
                color: sp.color,
              }}
            >
              {sp.char}
            </span>
          );
        })}
      </div>

      {/* Rainbow Trail */}
      <div
        className="nyan-trail"
        style={{
          left: mochiDirection === 1 ? (mochiX - trailLen) + 'px' : (mochiX + 144) + 'px',
          width: trailLen + 'px',
        }}
      >
        {RAINBOW_COLORS.map((_, idx) => {
          const colorIdx = (idx + Math.floor(rainbowOffset / 4)) % RAINBOW_COLORS.length;
          const color = RAINBOW_COLORS[colorIdx];
          return (
            <div
              key={idx}
              className="rainbow-stripe"
              style={{
                background: 'linear-gradient(' + (mochiDirection === 1 ? 'to left' : 'to right') + ', ' + color + ', transparent)',
              }}
            />
          );
        })}
      </div>

      {/* Mochi Cat */}
      <div
        className="mochi-container"
        style={{
          left: mochiX + 'px',
          top: mochiY + 'px',
          transform: 'scaleX(' + mochiDirection + ')',
        }}
      >
        <MochiSprite mood={mood} blinking={blinking} frame={frame} />
      </div>

      <div className="floor-line">{"─".repeat(300)}</div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// CARD COMPONENTS (for /agents, /inspect, /summary, etc.)
// ═══════════════════════════════════════════════════════════════════════════════

function RosterCard({ agents }) {
  return (
    <div className="card roster">
      <div className="card-header fg-dim">
        <span style={{width:'140px'}}>NAME</span>
        <span style={{width:'70px'}}>STATUS</span>
        <span style={{width:'60px'}}>CPU</span>
        <span style={{width:'60px'}}>MEM</span>
        <span style={{width:'80px'}}>TOK/MIN</span>
        <span style={{width:'80px'}}>LATENCY</span>
        <span style={{width:'100px'}}>OPTIMIZER</span>
      </div>
      <div className="fg-border card-divider">{"─".repeat(70)}</div>
      {agents.map((a, j) => (
        <div key={j} className="card-row">
          <span style={{width:'140px'}} className="fg-main">{a.name}</span>
          <span style={{width:'70px'}} className={a.status === 'HOT' ? 'fg-hot' : 'fg-green'}>{a.status}</span>
          <span style={{width:'60px'}} className="fg-dim">{a.cpu}%</span>
          <span style={{width:'60px'}} className="fg-dim">{a.mem}M</span>
          <span style={{width:'80px'}} className="fg-dim">{a.tok}</span>
          <span style={{width:'80px'}} className="fg-dim">{a.latency}ms</span>
          <span style={{width:'100px'}} className="fg-dim">{a.optimizer}</span>
        </div>
      ))}
    </div>
  );
}

function DetailCard({ agent }) {
  return (
    <div className="card detail">
      <div className="detail-title fg-pink bold">Agent: {agent.name}</div>
      <div className="detail-row"><span className="fg-dim">Status:</span> <span className={agent.status === 'HOT' ? 'fg-hot' : 'fg-green'}>{agent.status}</span></div>
      <div className="detail-row"><span className="fg-dim">CPU:</span> <span className="fg-main">{agent.cpu}%</span></div>
      <div className="detail-row"><span className="fg-dim">Memory:</span> <span className="fg-main">{agent.mem}MB</span></div>
      <div className="detail-row"><span className="fg-dim">Temp:</span> <span className="fg-main">{agent.temp}°C</span></div>
      <div className="detail-row"><span className="fg-dim">Tokens/min:</span> <span className="fg-main">{agent.tok}</span></div>
      <div className="detail-row"><span className="fg-dim">Latency:</span> <span className="fg-main">{agent.latency}ms</span></div>
      <div className="detail-row"><span className="fg-dim">Optimizer:</span> <span className="fg-main">{agent.optimizer}</span></div>
    </div>
  );
}

function SummaryCard() {
  const total = MOCK_AGENTS.length;
  const hot = MOCK_AGENTS.filter(a => a.status === 'HOT').length;
  const alerts = MOCK_ALERTS.length;
  const totalTok = MOCK_AGENTS.reduce((sum, a) => sum + a.tok, 0);
  const avgCpu = Math.floor(MOCK_AGENTS.reduce((sum, a) => sum + a.cpu, 0) / total);
  const mostActive = MOCK_AGENTS.reduce((max, a) => a.tok > max.tok ? a : max, MOCK_AGENTS[0]);

  return (
    <div className="card detail">
      <div className="detail-title fg-pink bold">System Summary</div>
      <div className="detail-row"><span className="fg-dim">Agents:</span> <span className="fg-green">{total}</span></div>
      <div className="detail-row"><span className="fg-dim">Hot:</span> <span className={hot > 0 ? 'fg-hot' : 'fg-dim'}>{hot}</span></div>
      <div className="detail-row"><span className="fg-dim">Alerts:</span> <span className={alerts > 0 ? 'fg-hot' : 'fg-dim'}>{alerts}</span></div>
      <div className="detail-row"><span className="fg-dim">Total tok/min:</span> <span className="fg-main">{totalTok}</span></div>
      <div className="detail-row"><span className="fg-dim">Avg CPU:</span> <span className="fg-main">{avgCpu}%</span></div>
      <div className="detail-row"><span className="fg-dim">Most active:</span> <span className="fg-pink">{mostActive.name}</span></div>
      <div className="detail-row"><span className="fg-dim">Last action:</span> <span className="fg-mint">prompt compression</span></div>
    </div>
  );
}

function AlertsCard() {
  return (
    <div className="card detail">
      <div className="detail-title fg-pink bold">Active Alerts</div>
      {MOCK_ALERTS.map((alert, idx) => (
        <div key={idx} className="fg-hot">{idx + 1}. {alert}</div>
      ))}
    </div>
  );
}

function CompareCard({ agent }) {
  return (
    <div className="card detail">
      <div className="detail-title fg-pink bold">{agent.name} Optimization Compare</div>
      <div className="detail-row fg-dim">Before: CPU 92% | Tokens 2450/min | Latency 610ms</div>
      <div className="detail-row fg-green">After:  CPU {agent.cpu}% | Tokens {agent.tok}/min | Latency {agent.latency}ms</div>
      <div className="detail-row fg-mint">Savings: 7% CPU | 18% tokens | 11% latency</div>
    </div>
  );
}

function DashboardCard() {
  return (
    <div className="card detail">
      <div className="detail-title fg-pink bold">Dashboard</div>
      <div className="detail-row"><span className="fg-dim">URL:</span> <span className="fg-green">{DASHBOARD_URL}</span></div>
      <div className="detail-row fg-dim">Open in browser for charts and trends.</div>
    </div>
  );
}

// ═══════════════════════════════════════════════════════════════════════════════
// MAIN APP
// ═══════════════════════════════════════════════════════════════════════════════

export default function App() {
  const [frame, setFrame] = useState(0);
  const [mood, setMood] = useState("idle");
  const [moodTimer, setMoodTimer] = useState(0);
  const [blinking, setBlinking] = useState(false);
  const [mochiX, setMochiX] = useState(50);
  const [mochiY, setMochiY] = useState(30);
  const [mochiDirection, setMochiDirection] = useState(1);
  const [sparkles, setSparkles] = useState([]);
  const [rainbowOffset, setRainbowOffset] = useState(0);
  const [inputBuffer, setInputBuffer] = useState("");
  const [transcript, setTranscript] = useState([
    { type: "system", prefix: "[system]", text: "Terminal session started.", cardData: null },
    { type: "system", prefix: "[system]", text: "Dashboard: " + DASHBOARD_URL + " (use /dashboard to start)", cardData: null }
  ]);
  
  const inputRef = useRef(null);
  const transcriptRef = useRef(null);
  const heroRef = useRef(null);
  const [heroWidth, setHeroWidth] = useState(800);
  const directionRef = useRef(1);

  // Update hero width on resize
  useEffect(() => {
    const updateWidth = () => {
      if (heroRef.current) {
        setHeroWidth(heroRef.current.offsetWidth);
      }
    };
    updateWidth();
    window.addEventListener('resize', updateWidth);
    return () => window.removeEventListener('resize', updateWidth);
  }, []);

  // Animation loop (~30fps)
  useEffect(() => {
    const interval = setInterval(() => {
      setFrame(f => f + 1);
      setRainbowOffset(o => o + 1);

      // Mochi movement
      const speed = mood === 'celebrate' ? 4 : mood === 'warning' ? 3 : 2;
      
      setMochiX(x => {
        let newX = x + speed * directionRef.current;
        const maxX = heroWidth - 160;

        if (newX >= maxX) {
          directionRef.current = -1;
          setMochiDirection(-1);
          // Burst sparkles on bounce
          for (let i = 0; i < 6; i++) {
            setSparkles(s => [...s, {
              x: maxX - Math.random() * 60,
              y: 20 + Math.random() * 80,
              char: SPARKLE_CHARS[Math.floor(Math.random() * SPARKLE_CHARS.length)],
              color: RAINBOW_COLORS[Math.floor(Math.random() * RAINBOW_COLORS.length)],
              age: 0,
              maxAge: 8 + Math.random() * 12,
            }]);
          }
          return maxX;
        } else if (newX <= 10) {
          directionRef.current = 1;
          setMochiDirection(1);
          for (let i = 0; i < 6; i++) {
            setSparkles(s => [...s, {
              x: 10 + Math.random() * 60,
              y: 20 + Math.random() * 80,
              char: SPARKLE_CHARS[Math.floor(Math.random() * SPARKLE_CHARS.length)],
              color: RAINBOW_COLORS[Math.floor(Math.random() * RAINBOW_COLORS.length)],
              age: 0,
              maxAge: 8 + Math.random() * 12,
            }]);
          }
          return 10;
        }
        return newX;
      });

      // Vertical bounce
      setMochiY(y => {
        const bounceAmp = mood === 'celebrate' ? 18 : mood === 'happy' ? 14 : 10;
        const period = mood === 'celebrate' ? 20 : 30;
        return 30 + Math.sin(frame * (2 * Math.PI / period)) * bounceAmp;
      });

      // Random blink
      if (Math.random() < 0.015) {
        setBlinking(true);
        setTimeout(() => setBlinking(false), 180);
      }

      // Random sparkles
      if (Math.random() < 0.25) {
        setSparkles(s => [...s, {
          x: Math.random() * heroWidth,
          y: Math.random() * 120,
          char: SPARKLE_CHARS[Math.floor(Math.random() * SPARKLE_CHARS.length)],
          color: RAINBOW_COLORS[Math.floor(Math.random() * RAINBOW_COLORS.length)],
          age: 0,
          maxAge: 5 + Math.random() * 15,
        }]);
      }

      // Age sparkles
      setSparkles(s => s.map(sp => ({ ...sp, age: sp.age + 1 })).filter(sp => sp.age < sp.maxAge));

      // Mood timer
      setMoodTimer(t => {
        if (t > 0) {
          if (t === 1) setMood("idle");
          return t - 1;
        }
        return t;
      });
    }, 33);

    return () => clearInterval(interval);
  }, [mood, frame, heroWidth]);

  // Auto-scroll transcript
  useEffect(() => {
    if (transcriptRef.current) {
      transcriptRef.current.scrollTop = transcriptRef.current.scrollHeight;
    }
  }, [transcript]);

  // ─────────────────────────────────────────────────────────────────────────────
  // COMMAND HANDLING (exactly like Python version)
  // ─────────────────────────────────────────────────────────────────────────────

  const handleCommand = useCallback((cmd) => {
    const cmdLower = cmd.toLowerCase().trim();

    if (cmdLower === "/help") {
      setTranscript(t => [...t, { type: "mochi", prefix: "Mochi", text: "Here are the available commands:", cardData: null }]);
      ["/agents", "/inspect <name>", "/alerts", "/summary", "/compare <name>", "/dashboard", "/replay", "/clear"].forEach(c => {
        setTranscript(t => [...t, { type: "system", prefix: "·", text: c, cardData: null }]);
      });
      setMood("happy"); setMoodTimer(90);
    } else if (cmdLower === "/agents") {
      setTranscript(t => [...t, { type: "mochi", prefix: "Mochi", text: "Here are your agents:", cardData: { type: "roster", agents: MOCK_AGENTS } }]);
      setMood("thinking"); setMoodTimer(60);
    } else if (cmdLower.startsWith("/inspect")) {
      const parts = cmd.split(/\s+/);
      if (parts.length > 1) {
        const name = parts.slice(1).join(' ').toLowerCase();
        const agent = MOCK_AGENTS.find(a => a.name.toLowerCase().includes(name));
        if (agent) {
          setTranscript(t => [...t, { type: "mochi", prefix: "Mochi", text: "Details for " + agent.name + ":", cardData: { type: "detail", agent } }]);
          if (agent.status === "HOT") {
            setTranscript(t => [...t, { type: "mochi", prefix: "Mochi", text: "This one is the busiest agent right now!", cardData: null }]);
          }
          setMood("thinking");
        } else {
          setTranscript(t => [...t, { type: "warning", prefix: "alert", text: "Agent '" + parts.slice(1).join(' ') + "' not found", cardData: null }]);
          setMood("sad");
        }
      } else {
        setTranscript(t => [...t, { type: "mochi", prefix: "Mochi", text: "Usage: /inspect <agent_name>", cardData: null }]);
      }
      setMoodTimer(60);
    } else if (cmdLower === "/alerts") {
      setTranscript(t => [...t, { type: "mochi", prefix: "Mochi", text: "Active alerts:", cardData: { type: "alerts" } }]);
      setTranscript(t => [...t, { type: "mochi", prefix: "Mochi", text: "Most pressure is coming from camera-agent.", cardData: null }]);
      setMood("warning"); setMoodTimer(100);
    } else if (cmdLower === "/summary") {
      setTranscript(t => [...t, { type: "mochi", prefix: "Mochi", text: "Here's the latest system summary:", cardData: { type: "summary" } }]);
      setMood("celebrate"); setMoodTimer(90);
    } else if (cmdLower.startsWith("/compare")) {
      const parts = cmd.split(/\s+/);
      if (parts.length > 1) {
        const name = parts.slice(1).join(' ').toLowerCase();
        const agent = MOCK_AGENTS.find(a => a.name.toLowerCase().includes(name));
        if (agent) {
          setTranscript(t => [...t, { type: "mochi", prefix: "Mochi", text: "Optimization comparison:", cardData: { type: "compare", agent } }]);
          setMood("celebrate");
        } else {
          setTranscript(t => [...t, { type: "warning", prefix: "alert", text: "Agent '" + parts.slice(1).join(' ') + "' not found", cardData: null }]);
          setMood("sad");
        }
      } else {
        setTranscript(t => [...t, { type: "mochi", prefix: "Mochi", text: "Usage: /compare <agent_name>", cardData: null }]);
      }
      setMoodTimer(90);
    } else if (cmdLower === "/dashboard") {
      setTranscript(t => [...t, { type: "mochi", prefix: "Mochi", text: "Opening dashboard...", cardData: null }]);
      setTranscript(t => [...t, { type: "mochi", prefix: "Mochi", text: "Dashboard shows charts and trends!", cardData: { type: "dashboard" } }]);
      window.open(DASHBOARD_URL, "_blank");
      setMood("happy"); setMoodTimer(60);
    } else if (cmdLower === "/replay") {
      setTranscript(t => [...t, { type: "mochi", prefix: "Mochi", text: "Replaying last optimization event...", cardData: null }]);
      setMood("celebrate"); setMoodTimer(120);
    } else if (cmdLower === "/clear") {
      setTranscript([{ type: "system", prefix: "[system]", text: "Transcript cleared.", cardData: null }]);
      setMood("idle"); setMoodTimer(0);
    } else {
      setTranscript(t => [...t, { type: "mochi", prefix: "Mochi", text: "Unknown command: " + cmd + ". Try /help", cardData: null }]);
      setMood("thinking"); setMoodTimer(60);
    }
  }, []);

  const handleNaturalLanguage = useCallback((text) => {
    const textLower = text.toLowerCase();

    if (/camera|vision|hot/.test(textLower)) {
      const agent = MOCK_AGENTS.find(a => a.name.includes("Camera"));
      setTranscript(t => [...t, { type: "mochi", prefix: "Mochi", text: "Camera Vision is the hottest agent!", cardData: null }]);
      setTranscript(t => [...t, { type: "mochi", prefix: "Mochi", text: "Details:", cardData: { type: "detail", agent } }]);
      setMood("warning"); setMoodTimer(100);
    } else if (/token|tok/.test(textLower)) {
      const totalTok = MOCK_AGENTS.reduce((sum, a) => sum + a.tok, 0);
      setTranscript(t => [...t, { type: "mochi", prefix: "Mochi", text: "Total token rate: " + totalTok + " tok/min", cardData: null }]);
      setMood("thinking"); setMoodTimer(60);
    } else if (/optimi/.test(textLower)) {
      setTranscript(t => [...t, { type: "mochi", prefix: "Mochi", text: "Optimizer already reduced waste from Camera Vision!", cardData: null }]);
      setTranscript(t => [...t, { type: "ok", prefix: "ok", text: "Prompt compression saved 38% tokens in the last run.", cardData: null }]);
      setMood("celebrate"); setMoodTimer(90);
    } else if (/hello|hi|hey/.test(textLower)) {
      setTranscript(t => [...t, { type: "mochi", prefix: "Mochi", text: "Hello! I'm here to help you understand your edge agents. ✦", cardData: null }]);
      setMood("happy"); setMoodTimer(90);
    } else if (/dashboard|web|browser/.test(textLower)) {
      setTranscript(t => [...t, { type: "mochi", prefix: "Mochi", text: "Here's your dashboard link:", cardData: { type: "dashboard" } }]);
      setMood("happy"); setMoodTimer(60);
    } else {
      setTranscript(t => [...t, { type: "mochi", prefix: "Mochi", text: "I'm not sure about that. Try /help for available commands.", cardData: null }]);
      setMood("thinking"); setMoodTimer(60);
    }
  }, []);

  const handleSubmit = () => {
    if (!inputBuffer.trim()) return;
    setTranscript(t => [...t, { type: "user", prefix: ">", text: inputBuffer.trim(), cardData: null }]);

    if (inputBuffer.startsWith("/")) {
      handleCommand(inputBuffer);
    } else {
      handleNaturalLanguage(inputBuffer);
    }
    setInputBuffer("");
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter') {
      handleSubmit();
    }
  };

  // Render card based on type
  const renderCard = (cardData) => {
    if (!cardData) return null;
    switch (cardData.type) {
      case 'roster': return <RosterCard agents={cardData.agents} />;
      case 'detail': return <DetailCard agent={cardData.agent} />;
      case 'summary': return <SummaryCard />;
      case 'alerts': return <AlertsCard />;
      case 'compare': return <CompareCard agent={cardData.agent} />;
      case 'dashboard': return <DashboardCard />;
      default: return null;
    }
  };

  // Calculate status bar values
  const totalAgents = MOCK_AGENTS.length;
  const hotAgents = MOCK_AGENTS.filter(a => a.status === 'HOT').length;
  const alertCount = MOCK_ALERTS.length;
  const totalTok = MOCK_AGENTS.reduce((sum, a) => sum + a.tok, 0);

  return (
    <div className="terminal-app" onClick={() => document.getElementById("cmd-input")?.focus()}>
      {/* Status Bar */}
      <div className="status-bar bg-surface2">
        <span className="fg-pink bold">Mochi</span>
        <span className="fg-dim"> | </span>
        <span className="fg-dim">mock</span>
        <span className="fg-dim"> | </span>
        <span className="fg-green bold">{totalAgents} agents</span>
        <span className="fg-dim"> | </span>
        <span className={hotAgents > 0 ? 'fg-hot bold' : 'fg-dim'}>{hotAgents} hot</span>
        <span className="fg-dim"> | </span>
        <span className={alertCount > 0 ? 'fg-hot' : 'fg-dim'}>{alertCount} alerts</span>
        <span className="fg-dim"> | </span>
        <span className="fg-dim">{totalTok} tok/min</span>
        <span className="fg-dim"> | </span>
        <span className="fg-dim">gemma3:1b</span>
        <span className="fg-dim"> | </span>
        <span className="fg-green">d: dashboard</span>
      </div>

      {/* Hero Section */}
      <div ref={heroRef} className="hero-wrapper">
        <MochiHero
          frame={frame}
          mood={mood}
          mochiX={mochiX}
          mochiY={mochiY}
          mochiDirection={mochiDirection}
          sparkles={sparkles}
          rainbowOffset={rainbowOffset}
          heroWidth={heroWidth}
          blinking={blinking}
        />
      </div>

      {/* Welcome Area */}
      <div className="welcome-text">
        <div className="fg-pink bold">Hi, I'm Mochi.</div>
        <div className="fg-dim">I explain edge-agent behavior and optimization.</div>
        <div className="fg-dim">Type /agents, /inspect camera-agent, or ask me anything.</div>
        <div className="fg-green">Dashboard running at {DASHBOARD_URL}</div>
      </div>
      
      <div className="divider fg-border">{"·".repeat(80)}</div>

      {/* Transcript */}
      <div className="transcript" ref={transcriptRef}>
        {transcript.map((msg, i) => (
          <div key={i} className="transcript-row">
            <span className="transcript-msg">
              <span className={
                msg.type === 'user' ? 'fg-green bold prefix' :
                msg.type === 'mochi' ? 'fg-pink bold prefix' :
                msg.type === 'warning' ? 'fg-hot bold prefix' :
                msg.type === 'ok' ? 'fg-green bold prefix' :
                'fg-dimmer prefix'
              }>{msg.prefix}</span>
              <span className={
                msg.type === 'system' ? 'fg-dimmer' :
                msg.type === 'warning' ? 'fg-hot' :
                msg.type === 'ok' ? 'fg-mint' :
                'fg-main'
              }>{msg.text}</span>
            </span>
            {renderCard(msg.cardData)}
          </div>
        ))}
        <div ref={inputRef} style={{ height: '10px' }} />
      </div>

      {/* Input Prompt */}
      <div className="prompt-area">
        <span className="fg-green bold">&gt;&nbsp;</span>
        <input
          id="cmd-input"
          type="text"
          value={inputBuffer}
          onChange={(e) => setInputBuffer(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask Mochi or type /help"
          autoFocus
          autoComplete="off"
          spellCheck="false"
        />
      </div>

      {/* Hints Bar */}
      <div className="hints-bar bg-surface2">
        <span className="fg-green bold">Enter</span> <span className="fg-dimmer">send</span>
        <span className="hint-sep">  </span>
        <span className="fg-green">↑↓</span> <span className="fg-dimmer">scroll</span>
        <span className="hint-sep">  </span>
        <span className="fg-green">/agents</span> <span className="fg-dimmer">list</span>
        <span className="hint-sep">  </span>
        <span className="fg-green">/dashboard</span> <span className="fg-dimmer">open</span>
        <span className="hint-sep">  </span>
        <span className="fg-green">q</span> <span className="fg-dimmer">quit</span>
      </div>
    </div>
  );
}

"use client";

// V1 backup — wavy-path implementation (pre-reference-code rewrite)
// Restore by copying this file's contents into animated-orb.tsx

interface AnimatedOrbProps {
  size?: number;
  className?: string;
}

function wavyPath(
  cx: number,
  cy: number,
  rx: number,
  ry: number,
  rotDeg: number,
  amp: number,
  freq: number,
): string {
  const rot = (rotDeg * Math.PI) / 180;
  const steps = 200;
  const pts: string[] = [];
  for (let i = 0; i <= steps; i++) {
    const t = (i / steps) * 2 * Math.PI;
    const wave = amp * Math.sin(freq * t);
    const ex = (rx + wave) * Math.cos(t);
    const ey = (ry + wave) * Math.sin(t);
    const x = cx + ex * Math.cos(rot) - ey * Math.sin(rot);
    const y = cy + ex * Math.sin(rot) + ey * Math.cos(rot);
    pts.push(`${i === 0 ? "M" : "L"}${x.toFixed(1)},${y.toFixed(1)}`);
  }
  return pts.join(" ") + " Z";
}

export default function AnimatedOrb({ size = 300, className = "" }: AnimatedOrbProps) {
  const r = size / 2;
  const cx = r;
  const cy = r;
  const baseR = r * 0.52;

  const spherePaths = Array.from({ length: 12 }, (_, i) => {
    const deg = i * 15;
    const rad = (deg * Math.PI) / 180;
    const ry = baseR * Math.abs(Math.cos(rad));
    return { deg, ry };
  });

  return (
    <div className={`relative ${className}`} style={{ width: size, height: size }} aria-hidden="true">
      <div className="absolute rounded-full border border-indigo-200/20" style={{ width: size * 1.7, height: size * 1.7, top: "50%", left: "50%", transform: "translate(-50%, -50%)", pointerEvents: "none" }} />
      <div className="absolute rounded-full border border-indigo-200/30" style={{ width: size * 1.35, height: size * 1.35, top: "50%", left: "50%", transform: "translate(-50%, -50%)", pointerEvents: "none" }} />
      <div className="absolute" style={{ width: size * 1.1, height: size * 1.1, top: "50%", left: "50%", transform: "translate(-50%, -50%)", pointerEvents: "none" }}>
        <div className="h-full w-full rounded-full border border-indigo-300/25" style={{ animation: "orb-wave-pulse 6s ease-in-out infinite" }} />
      </div>
      <svg viewBox={`0 0 ${size} ${size}`} fill="none" width={size} height={size} className="absolute inset-0" style={{ animation: "orb-spin 40s linear infinite" }}>
        {spherePaths.map(({ deg, ry }) => (
          <path key={`w-${deg}`} d={wavyPath(cx, cy, baseR, ry, deg, 3, 8)} stroke="rgba(99, 102, 241, 0.28)" strokeWidth="0.7" fill="none" />
        ))}
      </svg>
      <svg viewBox={`0 0 ${size} ${size}`} fill="none" width={size} height={size} className="absolute inset-0" style={{ animation: "orb-counter-spin 28s linear infinite" }}>
        <circle cx={cx} cy={cy} r={baseR * 0.9} stroke="rgba(165, 180, 252, 0.22)" strokeWidth="0.6" fill="none" />
        <circle cx={cx} cy={cy} r={baseR * 0.65} stroke="rgba(199, 210, 254, 0.30)" strokeWidth="0.6" fill="none" />
      </svg>
      <div className="absolute" style={{ width: size * 0.22, height: size * 0.22, top: "50%", left: "50%", transform: "translate(-50%, -50%)" }}>
        <div className="h-full w-full rounded-full" style={{ background: "radial-gradient(circle, rgba(255,255,255,1) 0%, rgba(199,210,254,0.6) 40%, transparent 70%)", animation: "orb-glow 4s ease-in-out infinite" }} />
      </div>
      <div className="absolute" style={{ width: 6, height: 6, top: "50%", left: "50%", ["--orbit-radius" as string]: `${r * 0.62}px`, animation: "orb-orbit 15s linear infinite" }}>
        <div className="h-1.5 w-1.5 rounded-full bg-indigo-400/70" />
      </div>
      <div className="absolute" style={{ width: 6, height: 6, top: "50%", left: "50%", ["--orbit-radius" as string]: `${r * 0.8}px`, animation: "orb-orbit 22s linear infinite reverse" }}>
        <div className="h-1 w-1 rounded-full bg-indigo-300/50" />
      </div>
    </div>
  );
}

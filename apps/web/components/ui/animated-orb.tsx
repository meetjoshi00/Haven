"use client";

import { useEffect, useRef, useState } from "react";

interface AnimatedOrbProps {
  size?: number;
  interactive?: boolean;
  className?: string;
}

/**
 * Build a sine-wave ring SVG path.
 * The fixed viewBox is 300×300 — all radii are in those units and stay
 * proportional regardless of the `size` prop (SVG scales via width/height).
 */
function buildSineRing(
  cx: number,
  cy: number,
  r: number,
  amp: number,
  freq: number,
  phase: number,
): string {
  const steps = 240;
  const pts: string[] = [];
  for (let i = 0; i <= steps; i++) {
    const t = (i / steps) * Math.PI * 2;
    const radius = r + Math.sin(t * freq + phase) * amp;
    const x = cx + Math.cos(t) * radius;
    const y = cy + Math.sin(t) * radius;
    pts.push(`${i === 0 ? "M" : "L"}${x.toFixed(2)},${y.toFixed(2)}`);
  }
  pts.push("Z");
  return pts.join(" ");
}

export default function AnimatedOrb({
  size = 300,
  interactive = true,
  className = "",
}: AnimatedOrbProps) {
  const stageRef = useRef<HTMLDivElement>(null);
  const [tilt, setTilt] = useState({ x: 0, y: 0 });

  useEffect(() => {
    if (!interactive) return;
    const stage = stageRef.current;
    if (!stage) return;

    const handleMove = (e: PointerEvent) => {
      const rect = stage.getBoundingClientRect();
      const cx = rect.left + rect.width / 2;
      const cy = rect.top + rect.height / 2;
      const nx = (e.clientX - cx) / Math.max(window.innerWidth, 1);
      const ny = (e.clientY - cy) / Math.max(window.innerHeight, 1);
      setTilt({ x: nx * 8, y: ny * 8 });
    };
    const handleLeave = () => setTilt({ x: 0, y: 0 });

    window.addEventListener("pointermove", handleMove, { passive: true });
    window.addEventListener("pointerleave", handleLeave);
    return () => {
      window.removeEventListener("pointermove", handleMove);
      window.removeEventListener("pointerleave", handleLeave);
    };
  }, [interactive]);

  // Dot distances scale with size (reference is 300px)
  const dot1Distance = size * 0.395; // ≈118px at size=300
  const dot2Distance = size * 0.467; // ≈140px at size=300

  return (
    // Outer wrapper: receives className (e.g. "mb-8") from the parent.
    // A bottom spacer accounts for the ripple rings' overflow so they
    // never visually clip into the content below.
    <div className={`inline-flex flex-col items-center ${className}`} aria-hidden="true">
      <div
        ref={stageRef}
        data-orb-scope=""
        style={{
          width: size,
          height: size,
          transform: `perspective(900px) rotateX(${-tilt.y}deg) rotateY(${tilt.x}deg)`,
          transition: "transform 240ms cubic-bezier(0.22, 1, 0.36, 1)",
        }}
      >
        {/* Soft ambient halo */}
        <div className="orb-halo" />

        {/* 4 staggered ripple rings emanating outward */}
        <div className="orb-ripple" />
        <div className="orb-ripple orb-ripple-2" />
        <div className="orb-ripple orb-ripple-3" />
        <div className="orb-ripple orb-ripple-4" />

        {/* Wireframe sphere — latitude + longitude ellipses, slow rotation */}
        <svg className="orb-wave orb-wave-spin" viewBox="0 0 300 300" fill="none">
          {[0.95, 0.78, 0.55, 0.30].map((sy, i) => (
            <ellipse
              key={`lat-${i}`}
              cx="150" cy="150" rx="92" ry={92 * sy}
              stroke="rgba(99, 102, 241, 0.22)"
              strokeWidth="0.8"
            />
          ))}
          {[0.95, 0.78, 0.55, 0.30].map((sy, i) => (
            <ellipse
              key={`lon-${i}`}
              cx="150" cy="150" rx={92 * sy} ry="92"
              stroke="rgba(99, 102, 241, 0.18)"
              strokeWidth="0.8"
            />
          ))}
        </svg>

        {/* Sine-wave outline rings — counter-rotating */}
        <svg className="orb-wave orb-wave-counter" viewBox="0 0 300 300" fill="none">
          <path
            d={buildSineRing(150, 150, 96, 4, 12, 0)}
            stroke="rgba(99, 102, 241, 0.45)"
            strokeWidth="1"
            fill="none"
          />
          <path
            d={buildSineRing(150, 150, 86, 3, 18, Math.PI / 3)}
            stroke="rgba(165, 180, 252, 0.42)"
            strokeWidth="0.8"
            fill="none"
          />
          <path
            d={buildSineRing(150, 150, 76, 2.5, 24, Math.PI / 2)}
            stroke="rgba(199, 210, 254, 0.55)"
            strokeWidth="0.7"
            fill="none"
          />
        </svg>

        {/* Translucent inner glow disc */}
        <div className="orb-glow" />

        {/* Pulsing pearl core */}
        <div className="orb-core" />

        {/* Orbital dot particles */}
        <div className="orb-orbit orb-orbit-1">
          <span style={{ transform: `translate(${dot1Distance}px)` }} />
        </div>
        <div className="orb-orbit orb-orbit-2">
          <span style={{ transform: `translate(${dot2Distance}px)` }} />
        </div>

        <style>{`
          [data-orb-scope] {
            position: relative;
            display: flex;
            align-items: center;
            justify-content: center;
            will-change: transform;
          }

          /* Ambient halo */
          [data-orb-scope] .orb-halo {
            position: absolute;
            inset: -50px;
            border-radius: 50%;
            background: radial-gradient(circle,
              rgba(165, 180, 252, 0.10) 0%,
              rgba(255, 255, 255, 0.0) 65%
            );
            filter: blur(40px);
            pointer-events: none;
            will-change: opacity, transform;
            animation: orb-halo-breathe 6s ease-in-out infinite;
          }
          @keyframes orb-halo-breathe {
            0%, 100% { opacity: 0.55; transform: scale(1); }
            50%      { opacity: 1;    transform: scale(1.06); }
          }

          /* Ripple rings */
          [data-orb-scope] .orb-ripple {
            position: absolute;
            inset: 0;
            border-radius: 50%;
            border: 1px solid rgba(99, 102, 241, 0.35);
            pointer-events: none;
            will-change: transform, opacity;
            animation: orb-ripple-out 4s cubic-bezier(0.22, 1, 0.36, 1) infinite;
          }
          [data-orb-scope] .orb-ripple-2 {
            animation-delay: 1s;
            border-color: rgba(165, 180, 252, 0.30);
          }
          [data-orb-scope] .orb-ripple-3 {
            animation-delay: 2s;
            border-color: rgba(99, 102, 241, 0.22);
          }
          [data-orb-scope] .orb-ripple-4 {
            animation-delay: 3s;
            border-color: rgba(165, 180, 252, 0.18);
          }
          @keyframes orb-ripple-out {
            0%   { transform: scale(0.55); opacity: 0; }
            20%  { opacity: 0.85; }
            100% { transform: scale(1.25); opacity: 0; }
          }

          /* Wireframe + sine-wave SVG layers */
          [data-orb-scope] .orb-wave {
            position: absolute;
            inset: 0;
            width: 100%;
            height: 100%;
            overflow: visible;
            will-change: transform;
          }
          [data-orb-scope] .orb-wave-spin    { animation: orb-spin 22s linear infinite; }
          [data-orb-scope] .orb-wave-counter { animation: orb-spin 32s linear infinite reverse; }

          /* Inner glow disc */
          [data-orb-scope] .orb-glow {
            position: absolute;
            inset: 30%;
            border-radius: 50%;
            background: radial-gradient(circle at 50% 50%,
              rgba(255, 255, 255, 0.85) 0%,
              rgba(244, 247, 255, 0.45) 35%,
              rgba(255, 255, 255, 0.0) 70%
            );
            backdrop-filter: blur(8px);
            -webkit-backdrop-filter: blur(8px);
            pointer-events: none;
            animation: orb-glow-breathe 4s ease-in-out infinite;
          }
          @keyframes orb-glow-breathe {
            0%, 100% { opacity: 0.7; transform: scale(1); }
            50%      { opacity: 1;   transform: scale(1.08); }
          }

          /* Pearl core */
          [data-orb-scope] .orb-core {
            position: absolute;
            inset: 44%;
            border-radius: 50%;
            background: radial-gradient(circle at 40% 40%,
              rgba(255, 255, 255, 1) 0%,
              rgba(199, 210, 254, 0.65) 50%,
              rgba(165, 180, 252, 0.30) 100%
            );
            box-shadow:
              0 0 16px rgba(165, 180, 252, 0.45),
              0 0 32px rgba(165, 180, 252, 0.22);
            animation: orb-core-pulse 2.8s ease-in-out infinite;
          }
          @keyframes orb-core-pulse {
            0%, 100% { transform: scale(1);    opacity: 0.85; }
            50%      { transform: scale(1.12); opacity: 1; }
          }

          /* Orbital dot particles */
          [data-orb-scope] .orb-orbit {
            position: absolute;
            inset: 0;
            border-radius: 50%;
            pointer-events: none;
            will-change: transform;
          }
          [data-orb-scope] .orb-orbit span {
            position: absolute;
            top: 50%;
            left: 50%;
            border-radius: 50%;
          }
          [data-orb-scope] .orb-orbit-1 { animation: orb-spin 9s linear infinite; }
          [data-orb-scope] .orb-orbit-1 span {
            width: 4px; height: 4px;
            margin: -2px 0 0 -2px;
            background: rgba(99, 102, 241, 0.85);
            box-shadow: 0 0 10px rgba(99, 102, 241, 0.60);
            animation: orb-dot-pulse 2.4s ease-in-out infinite;
          }
          [data-orb-scope] .orb-orbit-2 { animation: orb-spin 14s linear infinite reverse; }
          [data-orb-scope] .orb-orbit-2 span {
            width: 3px; height: 3px;
            margin: -1.5px 0 0 -1.5px;
            background: rgba(165, 180, 252, 0.85);
            box-shadow: 0 0 8px rgba(165, 180, 252, 0.55);
            animation: orb-dot-pulse 3.2s ease-in-out infinite 0.6s;
          }
          @keyframes orb-dot-pulse {
            0%, 100% { opacity: 0.65; }
            50%      { opacity: 1; }
          }

          /* Shared spin keyframe */
          @keyframes orb-spin {
            to { transform: rotate(360deg); }
          }

          /* Reduced motion */
          @media (prefers-reduced-motion: reduce) {
            [data-orb-scope] *,
            [data-orb-scope] {
              animation-duration: 0.001ms !important;
              animation-iteration-count: 1 !important;
              transition: none !important;
            }
          }
        `}</style>
      </div>

      {/* Bottom spacer: accounts for ripple rings expanding up to 1.25× the stage.
          Overflow = (1.25 - 1) / 2 × size. Add a little extra for safety. */}
      <div style={{ height: Math.round(size * 0.16) }} />
    </div>
  );
}

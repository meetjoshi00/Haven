"use client";

const WIDTH = 200;
const HEIGHT = 40;
const PADDING = 4;

interface SignalSparklineProps {
  label: string;
  data: number[];
  color: string;
  unit: string;
  peakIndices?: number[];
}

export default function SignalSparkline({
  label,
  data,
  color,
  unit,
  peakIndices = [],
}: SignalSparklineProps) {
  if (data.length < 2) {
    return (
      <div className="flex flex-col gap-1">
        <p className="text-xs text-muted-foreground">{label}</p>
        <div
          style={{ width: WIDTH, height: HEIGHT }}
          className="rounded border border-border bg-muted/30 flex items-center justify-center"
        >
          <span className="text-xs text-muted-foreground">—</span>
        </div>
      </div>
    );
  }

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const toX = (i: number) =>
    PADDING + (i / (data.length - 1)) * (WIDTH - PADDING * 2);
  const toY = (v: number) =>
    HEIGHT - PADDING - ((v - min) / range) * (HEIGHT - PADDING * 2);

  const points = data.map((v, i) => `${toX(i)},${toY(v)}`).join(" ");

  const last = data[data.length - 1];
  const lastLabel =
    last != null
      ? `${last.toFixed(2)} ${unit}`
      : "";

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center justify-between">
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="text-xs font-medium tabular-nums">{lastLabel}</p>
      </div>
      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        width={WIDTH}
        height={HEIGHT}
        className="overflow-visible rounded border border-border bg-muted/20"
        aria-hidden="true"
      >
        <polyline
          points={points}
          fill="none"
          stroke={color}
          strokeWidth={1.5}
          strokeLinejoin="round"
          strokeLinecap="round"
        />
        {/* Peak markers */}
        {peakIndices.map((pi) => {
          if (pi < 0 || pi >= data.length) return null;
          return (
            <circle
              key={pi}
              cx={toX(pi)}
              cy={toY(data[pi])}
              r={2.5}
              fill={color}
            />
          );
        })}
      </svg>
    </div>
  );
}

// src/components/football/FootballFallback.jsx
// Static SVG football for browsers/devices without WebGL. Built from the same truncated-icosahedron
// topology as the 3D mesh, so it is the same ball, not a different drawing.
import { useId, useMemo } from "react";
import { buildFlatProjection } from "./footballGeometry.js";

export default function FootballFallback({ size = 400 }: { size?: number }) {
  const uid = useId().replace(/:/g, "");
  const panels = useMemo(() => buildFlatProjection({ size }), [size]);
  const r = size / 2;
  return (
    <svg
      viewBox={`0 0 ${size} ${size}`}
      role="img"
      aria-label="Football"
      style={{ display: "block", width: "100%", height: "100%" }}
    >
      <defs>
        <clipPath id={`clip-${uid}`}>
          <circle cx={r} cy={r} r={r * 0.98} />
        </clipPath>
        <radialGradient id={`shade-${uid}`} cx="38%" cy="30%" r="80%">
          <stop offset="0%" stopColor="#fff" stopOpacity="0.10" />
          <stop offset="55%" stopColor="#000" stopOpacity="0" />
          <stop offset="100%" stopColor="#000" stopOpacity="0.45" />
        </radialGradient>
      </defs>
      <g clipPath={`url(#clip-${uid})`}>
        <circle cx={r} cy={r} r={r} fill="#efebe0" />
        {panels.map((p, i) => (
          <polygon
            key={i}
            points={p.points.map(([x, y]) => `${x.toFixed(1)},${y.toFixed(1)}`).join(" ")}
            fill={p.color === "black" ? "#17181b" : "#efebe0"}
            stroke="#1b1c1f"
            strokeWidth={size * 0.006}
            strokeLinejoin="round"
          />
        ))}
        <circle cx={r} cy={r} r={r} fill={`url(#shade-${uid})`} />
      </g>
    </svg>
  );
}

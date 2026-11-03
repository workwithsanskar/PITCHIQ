// src/components/football/footballGeometry.js
//
// Dependency-free geometry for a classic 32-panel football (truncated icosahedron).
// No three.js import on purpose: this file runs in Node for validation AND in the browser.
//
//   buildTruncatedIcosahedron()  -> exact topology (60 vertices, 12 pentagons, 20 hexagons)
//   buildFootballMeshData(opts)  -> renderable, seamed, slightly inflated mesh data
//
// Construction (no hand-placed polygons):
//   1. Regular icosahedron (12 vertices, 30 edges, 20 triangles).
//   2. Cut every edge at 1/3 and 2/3  -> 60 vertices.
//   3. Each icosahedron TRIANGLE becomes a HEXAGON  (20 white panels).
//   4. Each icosahedron VERTEX   becomes a PENTAGON (12 black panels).

const PHI = (1 + Math.sqrt(5)) / 2;

const add = (a, b) => [a[0] + b[0], a[1] + b[1], a[2] + b[2]];
const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const mul = (a, s) => [a[0] * s, a[1] * s, a[2] * s];
const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const cross = (a, b) => [
  a[1] * b[2] - a[2] * b[1],
  a[2] * b[0] - a[0] * b[2],
  a[0] * b[1] - a[1] * b[0],
];
const len = (a) => Math.hypot(a[0], a[1], a[2]);
const norm = (a) => mul(a, 1 / len(a));
const mean = (pts) => mul(pts.reduce(add, [0, 0, 0]), 1 / pts.length);
const smoothstep = (e0, e1, x) => {
  const t = Math.min(1, Math.max(0, (x - e0) / (e1 - e0)));
  return t * t * (3 - 2 * t);
};

/** Exact truncated-icosahedron topology on the unit sphere. */
export function buildTruncatedIcosahedron() {
  // 1. Regular icosahedron: cyclic permutations of (0, ±1, ±phi), normalised.
  const ico = [];
  for (const s1 of [-1, 1]) {
    for (const s2 of [-1, 1]) {
      ico.push(norm([0, s1, s2 * PHI]));
      ico.push(norm([s1, s2 * PHI, 0]));
      ico.push(norm([s2 * PHI, 0, s1]));
    }
  }

  // Adjacency from the shortest pairwise distance (the icosahedron edge length).
  const dist = (i, j) => len(sub(ico[i], ico[j]));
  let edgeLen = Infinity;
  for (let i = 0; i < 12; i++) for (let j = i + 1; j < 12; j++) edgeLen = Math.min(edgeLen, dist(i, j));
  const nbr = ico.map(() => []);
  for (let i = 0; i < 12; i++) {
    for (let j = i + 1; j < 12; j++) {
      if (Math.abs(dist(i, j) - edgeLen) < 1e-9) {
        nbr[i].push(j);
        nbr[j].push(i);
      }
    }
  }

  // Triangles = triples of mutually adjacent vertices, wound counter-clockwise from outside.
  const tris = [];
  for (let i = 0; i < 12; i++) {
    for (const j of nbr[i]) {
      if (j <= i) continue;
      for (const k of nbr[j]) {
        if (k <= j || !nbr[i].includes(k)) continue;
        const n = cross(sub(ico[j], ico[i]), sub(ico[k], ico[i]));
        tris.push(dot(n, add(add(ico[i], ico[j]), ico[k])) > 0 ? [i, j, k] : [i, k, j]);
      }
    }
  }

  // 2. Cut each directed edge a->b at 1/3 from a  => 60 shared vertices.
  const vertices = [];
  const cutIds = new Map();
  const cut = (a, b) => {
    const id = a * 12 + b;
    if (!cutIds.has(id)) {
      cutIds.set(id, vertices.length);
      vertices.push(add(mul(ico[a], 2 / 3), mul(ico[b], 1 / 3)));
    }
    return cutIds.get(id);
  };

  // 3. Hexagons from triangles (ccw preserved).
  const hexagons = tris.map(([a, b, c]) => [cut(a, b), cut(b, a), cut(b, c), cut(c, b), cut(c, a), cut(a, c)]);

  // 4. Pentagons from icosahedron vertices (neighbours sorted ccw around the vertex axis).
  const pentagons = ico.map((axis, v) => {
    const first = ico[nbr[v][0]];
    const u = norm(sub(first, mul(axis, dot(first, axis))));
    const w = cross(axis, u); // (u, w, axis) is right-handed
    const angle = (n) => Math.atan2(dot(ico[n], w), dot(ico[n], u));
    return [...nbr[v]].sort((p, q) => angle(p) - angle(q)).map((n) => cut(v, n));
  });

  // All 60 vertices are equidistant from the origin -> uniform scale to the unit sphere keeps panels planar.
  return { vertices: vertices.map(norm), pentagons, hexagons };
}

/**
 * Renderable mesh. Every panel is its own welded patch (so the seam is a real crease),
 * sunk into a groove along its boundary and gently inflated in the middle.
 * Returns { black, white, stats } where black = 12 pentagons, white = 20 hexagons.
 * Each group: { positions, uvs, colors, seam, indices } as typed arrays.
 */
export function buildFootballMeshData({
  radius = 1,
  subdivisions = 12,   // rows per wedge; 12 -> ~26k triangles total
  edgeBias = 1.8,      // >1 packs more rows near the seam so the groove is smooth
  grooveDepth = 0.006, // fine recessed seam, fraction of radius
  grooveWidth = 0.018, // narrow groove half-width (panel edge length ~0.40)
  pillow = 0.004,      // subtle panel crown, fraction of radius
  aoWidth = 0.030,     // tight seam shading falloff
  aoStrength = 0.40,   // restrained contact shading at the seam
  uvScale = 0.68,      // slightly enlarged micro-grain for visibility at hero size
} = {}) {
  const topo = buildTruncatedIcosahedron();
  const S = subdivisions;
  const groups = {
    black: { pos: [], uv: [], col: [], seam: [], idx: [] },
    white: { pos: [], uv: [], col: [], seam: [], idx: [] },
  };

  const buildPanel = (cornerIds, group, panelIndex) => {
    const g = groups[group];
    const corners = cornerIds.map((i) => topo.vertices[i]);
    const n = corners.length;
    const C = mean(corners);                    // flat panel centre (inside the sphere)
    const nC = norm(C);
    const ex = norm(sub(corners[0], C));        // tangent basis for planar grain UVs
    const ey = cross(nC, ex);
    const offU = (panelIndex * 0.37) % 1;
    const offV = (panelIndex * 0.61) % 1;

    const welded = new Map();                   // weld ONLY inside this panel
    const vertexAt = (p, d, h) => {
      const key = p.map((x) => Math.round(x * 1e6)).join(",");
      if (welded.has(key)) return welded.get(key);

      const dir = norm(p);
      const groove = grooveDepth * Math.pow(Math.max(0, 1 - d / grooveWidth), 2);
      const puff = pillow * Math.sin((Math.PI / 2) * Math.min(1, d / h));
      const r = radius * (1 - groove + puff);
      const seamShade = 1 - aoStrength * (1 - smoothstep(0, aoWidth, d));
      const panelVariation = 0.992 + ((panelIndex * 7) % 9) * 0.001;
      const shade = seamShade * panelVariation;
      const rel = sub(p, C);

      const index = g.pos.length / 3;
      g.pos.push(dir[0] * r, dir[1] * r, dir[2] * r);
      g.uv.push(dot(rel, ex) * uvScale + 0.5 + offU, dot(rel, ey) * uvScale + 0.5 + offV);
      g.col.push(shade, shade, shade);
      g.seam.push(d);
      welded.set(key, index);
      return index;
    };

    for (let i = 0; i < n; i++) {
      const A = corners[i];
      const B = corners[(i + 1) % n];
      const h = len(sub(mul(add(A, B), 0.5), C)); // centre -> edge distance (inradius)
      const rows = [];
      for (let r = 0; r <= S; r++) {
        const rho = 1 - Math.pow(1 - r / S, edgeBias); // 0 at centre, 1 at the seam
        const row = [];
        for (let j = 0; j <= r; j++) {
          const q = r === 0 ? A : add(mul(A, 1 - j / r), mul(B, j / r)); // point on edge AB
          const p = add(C, mul(sub(q, C), rho));
          row.push(vertexAt(p, h * (1 - rho), h));
        }
        rows.push(row);
      }
      const tri = (a, b, c) => {
        // force outward winding
        const pa = g.pos.slice(a * 3, a * 3 + 3);
        const pb = g.pos.slice(b * 3, b * 3 + 3);
        const pc = g.pos.slice(c * 3, c * 3 + 3);
        const nrm = cross(sub(pb, pa), sub(pc, pa));
        if (dot(nrm, add(add(pa, pb), pc)) >= 0) g.idx.push(a, b, c);
        else g.idx.push(a, c, b);
      };
      for (let r = 1; r <= S; r++) {
        for (let j = 0; j < r; j++) tri(rows[r - 1][j], rows[r][j], rows[r][j + 1]);
        for (let j = 0; j < r - 1; j++) tri(rows[r - 1][j], rows[r][j + 1], rows[r - 1][j + 1]);
      }
    }
  };

  topo.pentagons.forEach((p, i) => buildPanel(p, "black", i));
  topo.hexagons.forEach((p, i) => buildPanel(p, "white", 12 + i));

  const pack = (g) => ({
    positions: new Float32Array(g.pos),
    uvs: new Float32Array(g.uv),
    colors: new Float32Array(g.col),
    seam: new Float32Array(g.seam),
    indices: new Uint32Array(g.idx),
  });
  const black = pack(groups.black);
  const white = pack(groups.white);

  return {
    black,
    white,
    stats: {
      pentagons: topo.pentagons.length,
      hexagons: topo.hexagons.length,
      vertices: (black.positions.length + white.positions.length) / 3,
      triangles: (black.indices.length + white.indices.length) / 3,
      params: { radius, grooveDepth, pillow },
    },
  };
}

/** Fine, evenly spaced stitches that bridge the recessed seams on the ball surface. */
export function buildFootballStitchData({ radius = 1, spacing = 0.085, stitchLength = 0.022, lift = 0.0015 } = {}) {
  const topology = buildTruncatedIcosahedron();
  const edgeMap = new Map();
  for (const face of [...topology.pentagons, ...topology.hexagons]) {
    for (let index = 0; index < face.length; index++) {
      const a = face[index];
      const b = face[(index + 1) % face.length];
      const key = a < b ? `${a}:${b}` : `${b}:${a}`;
      if (!edgeMap.has(key)) edgeMap.set(key, [a, b]);
    }
  }

  const positions = [];
  for (const [aId, bId] of edgeMap.values()) {
    const a = topology.vertices[aId];
    const b = topology.vertices[bId];
    const edgeLength = len(sub(b, a));
    const count = Math.max(3, Math.round(edgeLength / spacing));
    for (let index = 0; index < count; index++) {
      const t = (index + 0.5) / count;
      const center = norm(add(mul(a, 1 - t), mul(b, t)));
      const tangent = norm(sub(b, mul(center, dot(b, center))));
      const across = norm(cross(center, tangent));
      for (const side of [-1, 1]) {
        const offset = add(center, mul(across, side * stitchLength / 2));
        const point = mul(norm(offset), radius + lift);
        positions.push(point[0], point[1], point[2]);
      }
    }
  }
  return new Float32Array(positions);
}

/**
 * Static 2D projection of the SAME topology, used by the no-WebGL fallback (SVG).
 * Returns polygons back-to-front: [{ color: "black" | "white", depth, points: [[x, y], ...] }]
 */
export function buildFlatProjection({ size = 400, yaw = 0.5, pitch = 0.5, samples = 8 } = {}) {
  const topo = buildTruncatedIcosahedron();
  const cy = Math.cos(yaw), sy = Math.sin(yaw), cx = Math.cos(pitch), sx = Math.sin(pitch);
  const rotate = ([x, y, z]) => {
    const x1 = x * cy + z * sy;
    const z1 = -x * sy + z * cy;
    return [x1, y * cx - z1 * sx, y * sx + z1 * cx];
  };
  const R = size / 2;
  const panels = [];
  const addPanel = (ids, color) => {
    const corners = ids.map((i) => topo.vertices[i]);
    const centre = rotate(norm(mean(corners)));
    if (centre[2] < -0.3) return; // fully on the far side
    const points = [];
    corners.forEach((A, i) => {
      const B = corners[(i + 1) % corners.length];
      for (let s = 0; s < samples; s++) {
        // sample along the edge and push back onto the sphere so seams curve like the real ball
        let [x, y, z] = rotate(norm(add(mul(A, 1 - s / samples), mul(B, s / samples))));
        if (z < 0) { const l = Math.hypot(x, y) || 1; x /= l; y /= l; } // clamp far-side points to the limb
        points.push([R + x * R * 0.98, R - y * R * 0.98]);
      }
    });
    panels.push({ color, depth: centre[2], points });
  };
  topo.hexagons.forEach((ids) => addPanel(ids, "white"));
  topo.pentagons.forEach((ids) => addPanel(ids, "black"));
  return panels.sort((a, b) => a.depth - b.depth);
}

// scripts/validate-football.mjs   ->   node scripts/validate-football.mjs
// Zero dependencies. Exits non-zero on any failure.
import assert from "node:assert/strict";
import { buildTruncatedIcosahedron, buildFootballMeshData, buildFootballStitchData } from "../src/components/football/footballGeometry.js";

const EPS = 1e-9;
const results = [];
const check = (name, fn) => {
  try { fn(); results.push(["PASS", name]); }
  catch (e) { results.push(["FAIL", `${name}  ->  ${e.message.split("\n")[0]}`]); process.exitCode = 1; }
};

const sub = (a, b) => [a[0] - b[0], a[1] - b[1], a[2] - b[2]];
const dot = (a, b) => a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
const cross = (a, b) => [a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0]];
const len = (a) => Math.hypot(a[0], a[1], a[2]);

// ---------- 1. Topology ----------
const topo = buildTruncatedIcosahedron();
const faces = [...topo.pentagons.map((f) => ({ f, kind: "P" })), ...topo.hexagons.map((f) => ({ f, kind: "H" }))];

const edgeMap = new Map(); // "a-b" (sorted) -> [face indices]
faces.forEach(({ f }, fi) => {
  f.forEach((v, i) => {
    const w = f[(i + 1) % f.length];
    const k = v < w ? `${v}-${w}` : `${w}-${v}`;
    if (!edgeMap.has(k)) edgeMap.set(k, []);
    edgeMap.get(k).push(fi);
  });
});

check("60 vertices", () => assert.equal(topo.vertices.length, 60));
check("12 pentagons / 20 hexagons / 32 faces", () => {
  assert.equal(topo.pentagons.length, 12);
  assert.equal(topo.hexagons.length, 20);
  assert.ok(topo.pentagons.every((f) => f.length === 5) && topo.hexagons.every((f) => f.length === 6));
});
check("90 edges", () => assert.equal(edgeMap.size, 90));
check("Euler characteristic V - E + F = 2", () => assert.equal(60 - edgeMap.size + faces.length, 2));
check("every edge shared by exactly 2 faces (closed surface)", () => {
  for (const [k, fs] of edgeMap) assert.equal(fs.length, 2, `edge ${k}`);
});
check("every vertex touches 3 faces: 1 pentagon + 2 hexagons", () => {
  for (let v = 0; v < 60; v++) {
    const touching = faces.filter(({ f }) => f.includes(v));
    assert.equal(touching.length, 3, `vertex ${v}`);
    assert.equal(touching.filter((t) => t.kind === "P").length, 1, `vertex ${v}`);
  }
});
check("no two pentagons share an edge; each pentagon has 5 hexagon neighbours", () => {
  for (const fs of edgeMap.values()) assert.ok(!(faces[fs[0]].kind === "P" && faces[fs[1]].kind === "P"));
  topo.pentagons.forEach((_, pi) => {
    const nb = new Set();
    for (const fs of edgeMap.values()) if (fs.includes(pi)) fs.filter((x) => x !== pi).forEach((x) => nb.add(x));
    assert.equal(nb.size, 5);
    assert.ok([...nb].every((x) => faces[x].kind === "H"));
  });
});
check("each hexagon has 3 pentagon + 3 hexagon neighbours, alternating", () => {
  topo.hexagons.forEach((h, hi) => {
    const fi = 12 + hi;
    const around = h.map((v, i) => {
      const w = h[(i + 1) % 6];
      const k = v < w ? `${v}-${w}` : `${w}-${v}`;
      return faces[edgeMap.get(k).find((x) => x !== fi)].kind;
    });
    assert.equal(around.filter((k) => k === "P").length, 3);
    for (let i = 0; i < 6; i++) assert.notEqual(around[i], around[(i + 1) % 6]);
  });
});
check("all 90 edges have equal length", () => {
  const ls = [...edgeMap.keys()].map((k) => { const [a, b] = k.split("-").map(Number); return len(sub(topo.vertices[a], topo.vertices[b])); });
  assert.ok(Math.max(...ls) - Math.min(...ls) < EPS);
});
check("all vertices on the unit sphere", () => {
  for (const v of topo.vertices) assert.ok(Math.abs(len(v) - 1) < EPS);
});
check("every panel is planar, regular (equal centre distance) and wound counter-clockwise from outside", () => {
  for (const { f } of faces) {
    const pts = f.map((i) => topo.vertices[i]);
    const c = pts.reduce((s, p) => [s[0] + p[0], s[1] + p[1], s[2] + p[2]], [0, 0, 0]).map((x) => x / pts.length);
    const n = cross(sub(pts[1], pts[0]), sub(pts[2], pts[0]));
    const nn = n.map((x) => x / len(n));
    assert.ok(dot(nn, c) > 0, "winding");
    for (const p of pts) assert.ok(Math.abs(dot(nn, sub(p, pts[0]))) < EPS, "planarity");
    const rs = pts.map((p) => len(sub(p, c)));
    assert.ok(Math.max(...rs) - Math.min(...rs) < EPS, "regularity");
  }
});

// ---------- 2. Render mesh ----------
const mesh = buildFootballMeshData();
const stitches = buildFootballStitchData();
const { grooveDepth, pillow } = mesh.stats.params;

check("mesh colour split: black = 12 pentagon patches, white = 20 hexagon patches", () => {
  const S = 12; // default subdivisions; a patch with n corners has 1 + n*S*(S+1)/2 welded vertices and n*S*S triangles
  assert.equal(mesh.black.indices.length / 3, 12 * 5 * S * S);
  assert.equal(mesh.white.indices.length / 3, 20 * 6 * S * S);
  assert.equal(mesh.black.positions.length / 3, 12 * (1 + (5 * S * (S + 1)) / 2));
  assert.equal(mesh.white.positions.length / 3, 20 * (1 + (6 * S * (S + 1)) / 2));
});
check("seam stitches are finite, paired line segments across the 90 shared edges", () => {
  assert.equal(stitches.length % 6, 0);
  assert.ok(stitches.length > 0);
  assert.ok([...stitches].every(Number.isFinite));
});
check("silhouette radius stays within the groove/pillow envelope", () => {
  for (const g of [mesh.black, mesh.white]) {
    for (let i = 0; i < g.positions.length; i += 3) {
      const r = len([g.positions[i], g.positions[i + 1], g.positions[i + 2]]);
      assert.ok(r >= 1 - grooveDepth - 1e-6 && r <= 1 + pillow + 1e-6, `r=${r}`);
    }
  }
});
check("every triangle faces outward and none are degenerate", () => {
  for (const g of [mesh.black, mesh.white]) {
    const P = (i) => [g.positions[i * 3], g.positions[i * 3 + 1], g.positions[i * 3 + 2]];
    for (let t = 0; t < g.indices.length; t += 3) {
      const a = P(g.indices[t]), b = P(g.indices[t + 1]), c = P(g.indices[t + 2]);
      const n = cross(sub(b, a), sub(c, a));
      assert.ok(len(n) > 1e-10, "degenerate triangle");
      assert.ok(dot(n, [a[0] + b[0] + c[0], a[1] + b[1] + c[1], a[2] + b[2] + c[2]]) > 0, "inward triangle");
    }
  }
});
check("watertight seams: every seam vertex is matched by the neighbouring panel (2 for edges, 3 for the 60 corners)", () => {
  const seamPts = [];
  for (const g of [mesh.black, mesh.white]) {
    for (let i = 0; i < g.seam.length; i++) if (g.seam[i] < 1e-9) seamPts.push([g.positions[i * 3], g.positions[i * 3 + 1], g.positions[i * 3 + 2]]);
  }
  let corners = 0;
  for (const p of seamPts) {
    const matches = seamPts.filter((q) => len(sub(p, q)) < 1e-5).length; // includes itself
    assert.ok(matches === 2 || matches === 3, `seam vertex matched ${matches} times`);
    if (matches === 3) corners++;
  }
  assert.equal(corners / 3, 60);
});

// ---------- report ----------
for (const [status, name] of results) console.log(`${status}  ${name}`);
console.log(`\nmesh: ${mesh.stats.vertices} vertices, ${mesh.stats.triangles} triangles`);
console.log(process.exitCode ? "\nVALIDATION FAILED" : "\nALL CHECKS PASSED");

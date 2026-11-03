// src/components/football/Football3D.jsx
// Rotating 32-panel football. Plain three.js inside a React effect (works with any React setup).
// Fills its parent element: size/position the PARENT to match the existing hero ball.
import { useEffect, useRef, useState } from "react";
import type { CSSProperties } from "react";
import * as THREE from "three";
import { RoomEnvironment } from "three/examples/jsm/environments/RoomEnvironment.js";
import { buildFootballMeshData, buildFootballStitchData, type FootballMeshGroup } from "./footballGeometry.js";
import FootballFallback from "./FootballFallback";

const SPIN_RAD_PER_SEC = 0.32;            // ~19.6 s per revolution, constant, time-based
const AXIS_TILT = { x: 0.42, z: -0.22 };  // fixed globe-style tilt; the axis never changes
const START_ANGLE = 0.6;                  // initial / reduced-motion pose (shows a pentagon + 3/4 view)
const FILL = 0.9;                         // ball diameter as a fraction of the container's short side
const RIM_COLOR = 0xd9f56c;               // pale, desaturated lime. Subtle edge separation only.

function webglAvailable() {
  return Boolean(window.WebGLRenderingContext || window.WebGL2RenderingContext);
}

// Tileable, deterministic micro-pebble height texture for synthetic-leather grain.
function makeGrainTexture(size = 512) {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext("2d");
  if (!ctx) {
    const bump = new THREE.CanvasTexture(canvas);
    bump.wrapS = bump.wrapT = THREE.RepeatWrapping;
    return bump;
  }
  ctx.fillStyle = "#808080";
  ctx.fillRect(0, 0, size, size);
  let seed = 1337;
  const rand = () => (seed = (seed * 1664525 + 1013904223) >>> 0) / 4294967296;
  for (let i = 0; i < 4200; i++) {
    const x = rand() * size, y = rand() * size, r = 1.1 + rand() * 1.2;
    const v = 60 + Math.floor(rand() * 145);
    ctx.fillStyle = `rgba(${v},${v},${v},0.52)`;
    for (const ox of [-size, 0, size]) {
      for (const oy of [-size, 0, size]) {
        ctx.beginPath();
        ctx.arc(x + ox, y + oy, r, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = "rgba(205,205,205,0.18)";
        ctx.beginPath();
        ctx.arc(x + ox - r * 0.22, y + oy - r * 0.26, r * 0.42, 0, Math.PI * 2);
        ctx.fill();
        ctx.fillStyle = `rgba(${v},${v},${v},0.52)`;
      }
    }
  }
  const bump = new THREE.CanvasTexture(canvas);
  bump.wrapS = bump.wrapT = THREE.RepeatWrapping;
  return bump;
}

// Very low-contrast, tileable roughness variation keeps highlights from looking airbrushed.
function makeRoughnessTexture(size = 512) {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = size;
  const ctx = canvas.getContext("2d");
  if (!ctx) return new THREE.CanvasTexture(canvas);
  ctx.fillStyle = "#e4e4e4";
  ctx.fillRect(0, 0, size, size);
  let seed = 7919;
  const rand = () => (seed = (seed * 1664525 + 1013904223) >>> 0) / 4294967296;
  for (let i = 0; i < 4200; i++) {
    const x = rand() * size, y = rand() * size, r = 1 + rand() * 1.3;
    ctx.fillStyle = "rgba(95,95,95,0.2)";
    for (const ox of [-size, 0, size]) {
      for (const oy of [-size, 0, size]) {
        ctx.beginPath();
        ctx.arc(x + ox, y + oy, r, 0, Math.PI * 2);
        ctx.fill();
      }
    }
  }
  const roughness = new THREE.CanvasTexture(canvas);
  roughness.wrapS = roughness.wrapT = THREE.RepeatWrapping;
  return roughness;
}

function toGeometry(group: FootballMeshGroup) {
  const g = new THREE.BufferGeometry();
  g.setAttribute("position", new THREE.BufferAttribute(group.positions, 3));
  g.setAttribute("uv", new THREE.BufferAttribute(group.uvs, 2));
  g.setAttribute("color", new THREE.BufferAttribute(group.colors, 3)); // baked seam shading
  g.setIndex(new THREE.BufferAttribute(group.indices, 1));
  const normals = new Float32Array(group.positions.length);
  for (let index = 0; index < group.positions.length; index += 3) {
    const x = group.positions[index], y = group.positions[index + 1], z = group.positions[index + 2];
    const length = Math.hypot(x, y, z) || 1;
    normals[index] = x / length;
    normals[index + 1] = y / length;
    normals[index + 2] = z / length;
  }
  g.setAttribute("normal", new THREE.BufferAttribute(normals, 3)); // continuous spherical shading across panel seams
  g.computeBoundingSphere();
  return g;
}

/**
 * staticAngle (radians) freezes the ball at a fixed rotation. Only for screenshot validation.
 */
interface Football3DProps {
  className?: string;
  style?: CSSProperties;
  staticAngle?: number;
}

export default function Football3D({ className, style, staticAngle }: Football3DProps) {
  const mountRef = useRef<HTMLDivElement | null>(null);
  const [useFallback, setUseFallback] = useState(false);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return undefined;
    if (!webglAvailable()) {
      setUseFallback(true);
      return undefined;
    }

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "high-performance" });
    } catch {
      setUseFallback(true);
      return undefined;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    renderer.outputColorSpace = THREE.SRGBColorSpace; // three < r152: renderer.outputEncoding = THREE.sRGBEncoding
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.0;
    renderer.setClearColor(0x000000, 0); // transparent: the hero background shows through
    const canvas = renderer.domElement;
    canvas.style.cssText = "display:block;width:100%;height:100%";
    canvas.setAttribute("aria-hidden", "true");
    mount.appendChild(canvas);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(28, 1, 0.1, 50);

    // Soft studio reflections without any network request.
    const pmrem = new THREE.PMREMGenerator(renderer);
    const room = new RoomEnvironment();
    const envMap = pmrem.fromScene(room, 0.04).texture;
    if (typeof room.dispose === "function") room.dispose();

    // Key (upper front), fill (soft, cool), rim (grazing, barely lime). Values assume three >= r155
    // (physical light units). On older three, divide each intensity by about PI.
    const key = new THREE.DirectionalLight(0xfff4e6, 3.0);
    key.position.set(-4, 4, 5);
    const fill = new THREE.DirectionalLight(0xcbd4cf, 0.72);
    fill.position.set(4, 0.5, 3);
    const rim = new THREE.DirectionalLight(RIM_COLOR, 0.62);
    rim.position.set(-2.5, 3, -4);
    scene.add(key, fill, rim);

    // Geometry and materials: created once, disposed on unmount.
    const data = buildFootballMeshData({ radius: 1, subdivisions: 12 });
    const whiteGeo = toGeometry(data.white);
    const blackGeo = toGeometry(data.black);
    const stitchPositions = buildFootballStitchData({ radius: 0.997, lift: 0.0002 });
    const stitchGeo = new THREE.BufferGeometry();
    stitchGeo.setAttribute("position", new THREE.BufferAttribute(stitchPositions, 3));
    stitchGeo.computeBoundingSphere();
    const stitchMat = new THREE.LineBasicMaterial({
      color: 0xb6b4ac,
      transparent: true,
      opacity: 0.84,
      depthWrite: false,
      toneMapped: false,
    });
    const grain = makeGrainTexture();
    grain.anisotropy = Math.min(4, renderer.capabilities.getMaxAnisotropy());
    const roughnessTexture = makeRoughnessTexture();
    roughnessTexture.anisotropy = Math.min(4, renderer.capabilities.getMaxAnisotropy());

    const whiteMat = new THREE.MeshPhysicalMaterial({
      color: 0xe9e7df,            // natural off-white, not digital white
      vertexColors: true,         // baked seam darkening from the geometry builder
      roughness: 0.62,
      roughnessMap: roughnessTexture,
      metalness: 0,
      clearcoat: 0.08,            // restrained satin response reveals the fine grain
      clearcoatRoughness: 0.68,
      bumpMap: grain,
      bumpScale: 0.3,             // fine pebble grain, restrained at normal size
      envMap,
      envMapIntensity: 0.38,
    });
    const blackMat = new THREE.MeshPhysicalMaterial({
      color: 0x17181b,            // charcoal, so it still separates from a near-black hero background
      vertexColors: true,
      roughness: 0.6,
      roughnessMap: roughnessTexture,
      metalness: 0,
      clearcoat: 0.09,
      clearcoatRoughness: 0.68,
      bumpMap: grain,
      bumpScale: 0.32,
      envMap,
      envMapIntensity: 0.42,
    });
    const ball = new THREE.Group();
    ball.add(
      new THREE.Mesh(whiteGeo, whiteMat),
      new THREE.Mesh(blackGeo, blackMat),
      new THREE.LineSegments(stitchGeo, stitchMat),
    );
    const tilt = new THREE.Group();
    tilt.rotation.set(AXIS_TILT.x, 0, AXIS_TILT.z);
    tilt.add(ball);
    scene.add(tilt);

    // ---- sizing: keep the container's box, fit the sphere inside it ----
    let angle = staticAngle ?? START_ANGLE;
    const draw = () => {
      ball.rotation.y = angle;
      renderer.render(scene, camera);
    };
    const resize = () => {
      const w = Math.max(1, mount.clientWidth);
      const h = Math.max(1, mount.clientHeight);
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      const half = THREE.MathUtils.degToRad(camera.fov / 2);
      const halfEff = camera.aspect >= 1 ? half : Math.atan(Math.tan(half) * camera.aspect);
      camera.position.set(0, 0, 1 / Math.sin(Math.atan(FILL * Math.tan(halfEff))));
      camera.lookAt(0, 0, 0);
      camera.updateProjectionMatrix();
      draw();
    };

    // ---- animation: time-based, no React state per frame, paused off-screen ----
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    const shouldAnimate = () => staticAngle === undefined && !reduceMotion.matches;
    let raf = 0, running = false, visible = true, pageVisible = !document.hidden, last = 0;
    const frame = (now: number) => {
      raf = requestAnimationFrame(frame);
      const dt = Math.min(0.05, (now - last) / 1000); // clamp so a background tab never causes a jump
      last = now;
      angle = (angle + dt * SPIN_RAD_PER_SEC) % (Math.PI * 2);
      draw();
    };
    const start = () => {
      if (running || !visible || !pageVisible || !shouldAnimate()) return;
      running = true;
      last = performance.now();
      raf = requestAnimationFrame(frame);
    };
    const stop = () => {
      running = false;
      cancelAnimationFrame(raf);
    };
    const onMotionChange = () => {
      stop();
      if (shouldAnimate()) start();
      else draw();
    };
    const onVisibilityChange = () => {
      pageVisible = !document.hidden;
      if (pageVisible) start();
      else stop();
    };
    reduceMotion.addEventListener("change", onMotionChange);
    document.addEventListener("visibilitychange", onVisibilityChange);

    const onLost = (e: Event) => {
      e.preventDefault();
      stop();
      canvas.style.display = "none";
      setUseFallback(true);
    };
    canvas.addEventListener("webglcontextlost", onLost);

    const ro = new ResizeObserver(resize);
    ro.observe(mount);
    const io =
      "IntersectionObserver" in window
        ? new IntersectionObserver(([entry]) => {
            visible = entry.isIntersecting;
            if (visible) start();
            else stop();
          })
        : null;
    if (io) io.observe(mount);

    resize(); // first frame
    mount.dataset.footballReady = "true";
    if (!io) start();

    return () => {
      stop();
      ro.disconnect();
      if (io) io.disconnect();
      reduceMotion.removeEventListener("change", onMotionChange);
      document.removeEventListener("visibilitychange", onVisibilityChange);
      canvas.removeEventListener("webglcontextlost", onLost);
      whiteGeo.dispose();
      blackGeo.dispose();
      stitchGeo.dispose();
      whiteMat.dispose();
      blackMat.dispose();
      stitchMat.dispose();
      grain.dispose();
      roughnessTexture.dispose();
      envMap.dispose();
      pmrem.dispose();
      renderer.dispose();
      renderer.forceContextLoss();
      canvas.remove();
      delete mount.dataset.footballReady;
    };
  }, [staticAngle]);

  return (
    <div
      ref={mountRef}
      className={className}
      style={{ position: "relative", width: "100%", height: "100%", ...style }}
      role="img"
      aria-label="Rotating football"
    >
      {useFallback ? <FootballFallback /> : null}
    </div>
  );
}

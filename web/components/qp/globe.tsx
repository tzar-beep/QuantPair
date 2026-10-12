"use client";
import { useEffect, useRef } from "react";
import createGlobe from "cobe";

// Major exchange cities [lat, lon]
const CITIES: [number, number][] = [
  [40.71, -74.01], [51.51, -0.13], [35.68, 139.69], [22.32, 114.17], [1.35, 103.82],
  [50.11, 8.68], [41.88, -87.63], [-33.87, 151.21], [19.08, 72.88], [43.65, -79.38],
];
// Pairs of cities linked by arcs (indices into CITIES)
const LINKS: [number, number][] = [[0, 1], [1, 5], [0, 6], [6, 9], [1, 8], [8, 4], [4, 3], [3, 2], [2, 7], [0, 2], [5, 3]];

const R_FRAC = 0.8;      // cobe sphere radius as a fraction of half the canvas
const THETA = 0.25;

type V = [number, number, number];
// Same conversion cobe uses for markers.
const toVec = ([lat, lon]: [number, number]): V => {
  const p = (lat * Math.PI) / 180, l = (lon * Math.PI) / 180 - Math.PI, c = Math.cos(p);
  return [-c * Math.cos(l), Math.sin(p), c * Math.sin(l)];
};

/** Project a world vector to canvas pixels using cobe's rotation matrix L(theta, phi). */
function project(v: V, phi: number, size: number, lift = 1): [number, number, boolean] {
  const c = Math.cos(THETA), e = Math.sin(THETA), d = Math.cos(phi), f = Math.sin(phi);
  const hx = d * v[0] + f * v[2];
  const hy = f * e * v[0] + c * v[1] - d * e * v[2];
  const hz = -f * c * v[0] + e * v[1] + d * c * v[2];
  const r = R_FRAC * lift;
  return [((hx * r + 1) / 2) * size, ((1 - hy * r) / 2) * size, hz > 0.02];
}

function slerp(a: V, b: V, t: number): V {
  const dot = Math.min(1, Math.max(-1, a[0] * b[0] + a[1] * b[1] + a[2] * b[2]));
  const w = Math.acos(dot);
  if (w < 1e-6) return a;
  const s1 = Math.sin((1 - t) * w) / Math.sin(w), s2 = Math.sin(t * w) / Math.sin(w);
  return [a[0] * s1 + b[0] * s2, a[1] * s1 + b[1] * s2, a[2] * s1 + b[2] * s2];
}

export function Globe() {
  const ref = useRef<HTMLCanvasElement>(null);
  const arcs = useRef<HTMLCanvasElement>(null);
  useEffect(() => {
    if (!ref.current || !arcs.current) return;
    const arcCanvas = arcs.current;
    let disposed = false;
    let phi = 0.6;
    let width = ref.current.offsetWidth;
    const onResize = () => { if (ref.current) width = ref.current.offsetWidth; };
    window.addEventListener("resize", onResize);
    const ctx = arcs.current.getContext("2d")!;
    const vecs = CITIES.map(toVec);
    let t = 0;

    const drawArcs = () => {
      if (disposed) return;
      const c = arcCanvas;
      const size = width * 2;
      if (c.width !== size) { c.width = size; c.height = size; }
      ctx.clearRect(0, 0, size, size);
      ctx.save();
      ctx.beginPath();
      ctx.arc(size / 2, size / 2, (size / 2) * R_FRAC * 0.995, 0, Math.PI * 2);
      ctx.clip();
      t += 0.006;
      LINKS.forEach(([i, j], k) => {
        const a = vecs[i], b = vecs[j];
        const dot = a[0] * b[0] + a[1] * b[1] + a[2] * b[2];
        const height = 0.03 + 0.05 * (1 - dot) / 2;    // gentle bulge; longer links rise slightly higher
        const pts: [number, number, boolean][] = [];
        for (let s = 0; s <= 48; s++) {
          const u = s / 48;
          pts.push(project(slerp(a, b, u), phi, size, 1 + height * Math.sin(Math.PI * u)));
        }
        ctx.lineWidth = 3;
        ctx.strokeStyle = "rgba(62,224,176,0.85)";
        ctx.beginPath();
        let pen = false;
        pts.forEach(([x, y, vis]) => {
          if (!vis) { pen = false; return; }
          if (pen) ctx.lineTo(x, y); else { ctx.moveTo(x, y); pen = true; }
        });
        ctx.stroke();
        // travelling pulse along each link
        const u = (t + k * 0.13) % 1;
        const [px, py, pv] = project(slerp(a, b, u), phi, size, 1 + height * Math.sin(Math.PI * u));
        if (pv) {
          ctx.fillStyle = "#3ee0b0";
          ctx.beginPath(); ctx.arc(px, py, 4.5, 0, Math.PI * 2); ctx.fill();
        }
      });
      ctx.restore();
    };

    const globe = createGlobe(ref.current, {
      devicePixelRatio: 2, width: width * 2, height: width * 2, phi, theta: THETA,
      dark: 1, diffuse: 1.2, mapSamples: 20000, mapBrightness: 7,
      baseColor: [0.16, 0.26, 0.42], markerColor: [0.06, 0.62, 0.46], glowColor: [0.89, 0.92, 0.96],
      markers: CITIES.map((location) => ({ location, size: 0.07 })),
      onRender: (s) => {
        phi += 0.0035;
        s.phi = phi;
        s.width = width * 2;
        s.height = width * 2;
        drawArcs();
      },
    });
    ref.current.style.opacity = "1";
    arcs.current.style.opacity = "1";
    return () => { disposed = true; globe.destroy(); window.removeEventListener("resize", onResize); };
  }, []);
  return (
    <div className="relative mx-auto aspect-square w-full max-w-[580px]">
      <canvas ref={ref} className="size-full opacity-0 transition-opacity duration-1000 [contain:layout_paint_size]" />
      <canvas ref={arcs} className="pointer-events-none absolute inset-0 size-full opacity-0 transition-opacity duration-1000" />
    </div>
  );
}

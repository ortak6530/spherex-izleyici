import { useEffect, useRef, useState } from "react";
import * as THREE from "three";

import { GALAXY, armPitchB, detectQuality, generateGalaxy, particleBudget } from "./galaxyModel";

// Background magnification (camera zoom). 1 = original framing (camera distance 1.85 landscape /
// 2.9 portrait); 1.4 = 40 % larger (2026-11-14). The canvas is fixed full-screen, so any value >= 1
// still covers the whole viewport; the rotation animation is unaffected.
const GALAXY_ZOOM = 1.4;

const VERTEX = /* glsl */ `
  uniform float uTime;
  uniform float uPixelRatio;
  uniform float uSize;
  uniform float uOmega0;
  uniform float uRSoft;
  uniform float uOmegaP;
  uniform float uArms;
  uniform float uPitchB;
  uniform float uR0;
  attribute float aRadius;
  attribute float aAngle;
  attribute float aHeight;
  attribute float aSize;
  attribute float aKind;
  attribute vec3 color;
  varying vec3 vColor;

  void main() {
    float r = aRadius;
    // Differential rotation: inner stars orbit faster (omega ~ 1/r, flat rotation curve)
    float omega = uOmega0 / (r + uRSoft);
    float theta = aAngle + omega * uTime;

    // Density-wave arms: rigid trailing log-spiral rotating at the pattern speed
    float spiral = -log(max(r, uR0) / uR0) / uPitchB;
    float d = theta - uOmegaP * uTime - spiral;
    float arm = pow(0.5 + 0.5 * cos(uArms * d), 4.0);
    float armMask = smoothstep(0.10, 0.32, r) * (1.0 - smoothstep(1.35, 1.7, r));
    float boost = aKind > 0.5 ? 1.1 : mix(0.12, 1.9, arm * armMask + (1.0 - armMask) * 0.35);

    vec3 pos = vec3(cos(theta) * r, aHeight, sin(theta) * r);
    vec4 mv = modelViewMatrix * vec4(pos, 1.0);
    gl_Position = projectionMatrix * mv;
    gl_PointSize = aSize * uSize * uPixelRatio * sqrt(boost) / -mv.z;
    vColor = color * boost;
  }
`;

const FRAGMENT = /* glsl */ `
  uniform float uOpacity;
  varying vec3 vColor;
  void main() {
    float d = length(gl_PointCoord - 0.5);
    if (d > 0.5) discard;
    float a = pow(1.0 - d * 2.0, 1.8) * uOpacity;
    gl_FragColor = vec4(vColor * a, a);
  }
`;

function buildStarfield(count: number): THREE.Points {
  const pos = new Float32Array(count * 3);
  let s = 7;
  const rnd = () => (s = (s * 16807) % 2147483647) / 2147483647;
  for (let i = 0; i < count; i++) {
    const u = rnd() * 2 - 1;
    const phi = rnd() * Math.PI * 2;
    const k = Math.sqrt(1 - u * u);
    pos.set([9 * k * Math.cos(phi), 9 * u, 9 * k * Math.sin(phi)], i * 3);
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
  const mat = new THREE.PointsMaterial({
    color: 0xc7d6ff,
    size: 1.1,
    sizeAttenuation: false,
    transparent: true,
    opacity: 0.45,
    depthWrite: false,
  });
  return new THREE.Points(geo, mat);
}

/**
 * Slowly rotating particle galaxy behind the UI. Pauses when the tab is hidden, renders a single
 * still frame with prefers-reduced-motion, and lowers the particle count on weak devices.
 */
function webglAvailable(): boolean {
  try {
    const c = document.createElement("canvas");
    return !!(c.getContext("webgl2") || c.getContext("webgl"));
  } catch {
    return false;
  }
}

export default function GalaxyBackground() {
  const hostRef = useRef<HTMLDivElement>(null);
  const [failed] = useState(() => !webglAvailable());

  useEffect(() => {
    const host = hostRef.current;
    if (!host || failed) return;

    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: false, alpha: true, powerPreference: "low-power" });
    } catch {
      return; // the CSS backdrop stays visible
    }
    const nav = navigator as Navigator & { deviceMemory?: number };
    const quality = detectQuality({
      hardwareConcurrency: nav.hardwareConcurrency,
      deviceMemory: nav.deviceMemory,
      coarsePointer: window.matchMedia("(pointer: coarse)").matches,
    });
    const pixelRatio = Math.min(window.devicePixelRatio || 1, quality === "high" ? 1.5 : 1.25);
    renderer.setPixelRatio(pixelRatio);
    renderer.setClearColor(0x000000, 0);
    host.appendChild(renderer.domElement);
    renderer.domElement.setAttribute("aria-hidden", "true");

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(50, 1, 0.01, 50);
    camera.zoom = GALAXY_ZOOM;

    const model = generateGalaxy(particleBudget(quality));
    const geo = new THREE.BufferGeometry();
    // Positions are computed in the shader; a dummy attribute keeps three.js happy
    geo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(model.count * 3), 3));
    geo.setAttribute("aRadius", new THREE.BufferAttribute(model.radius, 1));
    geo.setAttribute("aAngle", new THREE.BufferAttribute(model.angle, 1));
    geo.setAttribute("aHeight", new THREE.BufferAttribute(model.height, 1));
    geo.setAttribute("aSize", new THREE.BufferAttribute(model.size, 1));
    geo.setAttribute("aKind", new THREE.BufferAttribute(model.kind, 1));
    geo.setAttribute("color", new THREE.BufferAttribute(model.color, 3));
    geo.boundingSphere = new THREE.Sphere(new THREE.Vector3(), GALAXY.rMax + 0.2);

    const uniforms = {
      uTime: { value: 240 },
      uPixelRatio: { value: pixelRatio },
      uSize: { value: 4.2 * GALAXY_ZOOM }, // points grow with the zoom, so the disk does not look sparser
      uOpacity: { value: 0.8 },
      uOmega0: { value: GALAXY.omega0 },
      uRSoft: { value: GALAXY.rSoft },
      uOmegaP: { value: GALAXY.omegaP },
      uArms: { value: GALAXY.arms },
      uPitchB: { value: armPitchB },
      uR0: { value: GALAXY.r0 },
    };
    const material = new THREE.ShaderMaterial({
      vertexShader: VERTEX,
      fragmentShader: FRAGMENT,
      uniforms,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
    });
    const galaxy = new THREE.Points(geo, material);
    galaxy.rotation.z = 0.32; // slight tilt for a less "posed" look
    scene.add(galaxy);
    const stars = buildStarfield(quality === "low" ? 700 : 1800);
    scene.add(stars);

    const resize = () => {
      const w = window.innerWidth;
      const h = window.innerHeight;
      renderer.setSize(w, h, false);
      renderer.domElement.style.width = "100%";
      renderer.domElement.style.height = "100%";
      camera.aspect = w / h;
      // Portrait screens: pull back so the disk still fits
      const dist = w / h < 1 ? 2.9 : 1.85;
      camera.position.set(0, dist * 0.56, dist * 0.83);
      camera.lookAt(0, 0, 0);
      galaxy.position.x = w / h > 1.3 ? 0.55 : 0;
      camera.updateProjectionMatrix();
    };
    resize();
    window.addEventListener("resize", resize);

    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let raf = 0;
    let last = performance.now();
    // FPS probe: if frames are slow, draw fewer particles (at most twice)
    let probeFrames = 0;
    let probeStart = last;
    let reductions = 0;
    let drawCount = model.count;

    const frame = (now: number) => {
      const dt = Math.min((now - last) / 1000, 0.1); // cap: no jump after tab switches
      last = now;
      uniforms.uTime.value += dt;
      renderer.render(scene, camera);

      probeFrames++;
      if (now - probeStart > 2500) {
        const fps = (probeFrames * 1000) / (now - probeStart);
        if (fps < 45 && reductions < 2 && drawCount > 8000) {
          drawCount = Math.floor(drawCount / 2);
          geo.setDrawRange(0, drawCount);
          reductions++;
        }
        probeFrames = 0;
        probeStart = now;
      }
      raf = requestAnimationFrame(frame);
    };

    const start = () => {
      cancelAnimationFrame(raf);
      if (reduceMotion.matches) {
        renderer.render(scene, camera); // one still frame
        return;
      }
      last = performance.now();
      probeStart = last;
      probeFrames = 0;
      raf = requestAnimationFrame(frame);
    };
    const stop = () => cancelAnimationFrame(raf);
    const onVisibility = () => (document.hidden ? stop() : start());
    const onMotionPref = () => start();

    document.addEventListener("visibilitychange", onVisibility);
    reduceMotion.addEventListener("change", onMotionPref);
    start();

    return () => {
      stop();
      window.removeEventListener("resize", resize);
      document.removeEventListener("visibilitychange", onVisibility);
      reduceMotion.removeEventListener("change", onMotionPref);
      geo.dispose();
      material.dispose();
      stars.geometry.dispose();
      (stars.material as THREE.Material).dispose();
      renderer.dispose();
      renderer.domElement.remove();
    };
  }, [failed]);

  return (
    <div aria-hidden="true" className="pointer-events-none fixed inset-0 -z-10">
      {failed ? (
        <div className="h-full w-full bg-[radial-gradient(ellipse_at_65%_45%,#1e2a4a_0%,#050816_60%)]" />
      ) : (
        <div ref={hostRef} className="h-full w-full" />
      )}
      {/* Readability veil: keeps UI text contrast high over the brightest parts of the galaxy */}
      {/* Slightly darker since GALAXY_ZOOM made the bright core larger (was 0 / 0.35 / 0.8) */}
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_center,rgb(5_8_22/0.12)_0%,rgb(5_8_22/0.45)_55%,rgb(5_8_22/0.85)_100%)]" />
    </div>
  );
}

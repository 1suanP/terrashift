/**
 * EarthGlobe - realistic, interactive 3D Earth (three.js).
 *
 * Base planet
 *   - NASA Blue Marble day colour, city lights on the night side
 *   - terrain relief from a normal map, sun glint on water from an ocean mask
 *   - separate cloud layer that drifts on its own, with cloud shadows on the ground
 *   - thin blue atmosphere: limb scattering on the surface + a soft outer glow
 *   - sun either follows the camera (always a lit view) or sits at its real position for "now"
 *   - 23.4° axial tilt when viewed from afar, easing to north-up when zoomed in
 * Interaction (unchanged API): orbit/zoom, click to pick lat/lon, drag a box, fly-to,
 * reset, marker, region highlight, and a data overlay painted into a canvas.
 */
import { forwardRef, useEffect, useImperativeHandle, useRef } from 'react';
import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import type { BBox, LatLon } from '../lib/geo';
import { boxFromCorners, latLonToVector3, vector3ToLatLon } from '../lib/geo';
import {
  atmosphereFragment, atmosphereVertex, cloudFragment, cloudVertex, earthFragment, earthVertex,
  overlayFragment, overlayVertex, subsolarPoint,
} from '../lib/earthShaders';

export interface GlobeHandle {
  flyTo: (target: LatLon, distance?: number) => void;
  reset: () => void;
  zoomBy: (factor: number) => void;
}

export type SunMode = 'camera' | 'real';

interface Props {
  marker: LatLon | null;
  region: BBox | null;
  /** Place name drawn next to the selection; hidden when that side faces away. */
  label?: { lat: number; lon: number; text: string } | null;
  drawMode: boolean;
  overlay: HTMLCanvasElement | null;
  overlayVersion: number;
  autoRotate: boolean;
  clouds: boolean;
  sunMode: SunMode;
  showGrid: boolean;
  onPick: (p: LatLon) => void;
  onRegion: (box: BBox) => void;
  onHover?: (p: LatLon | null) => void;
  onReady?: () => void;
  onStats?: (s: { fps: number; tier: string }) => void;
}

const DEFAULT_VIEW: LatLon = { lat: 18, lon: -35 };
const MIN_DIST = 1.22;
const MAX_DIST = 6;
const AXIAL_TILT = THREE.MathUtils.degToRad(23.44);
const CLOUD_SPEED = 0.0035; // rad/s, about one lap every 30 minutes
const IDLE_BEFORE_SPIN_MS = 6000;

const defaultDistance = (aspect: number) => (aspect < 0.8 ? 4.4 : 3.1);

/** Line loop tracing a lat/lon box on the sphere. */
const boxOutline = (b: BBox, r: number): THREE.Vector3[] => {
  const pts: THREE.Vector3[] = [];
  const steps = 48;
  for (let i = 0; i <= steps; i++) pts.push(latLonToVector3(b.max_lat, b.min_lon + ((b.max_lon - b.min_lon) * i) / steps, r));
  for (let i = 0; i <= steps; i++) pts.push(latLonToVector3(b.max_lat - ((b.max_lat - b.min_lat) * i) / steps, b.max_lon, r));
  for (let i = 0; i <= steps; i++) pts.push(latLonToVector3(b.min_lat, b.max_lon - ((b.max_lon - b.min_lon) * i) / steps, r));
  for (let i = 0; i <= steps; i++) pts.push(latLonToVector3(b.min_lat + ((b.max_lat - b.min_lat) * i) / steps, b.min_lon, r));
  return pts;
};

/** Spherical patch exactly covering a lat/lon box (same UV convention as the Earth). */
const boxPatch = (b: BBox, r: number) =>
  new THREE.SphereGeometry(
    r, 48, 24,
    ((b.min_lon + 180) / 360) * Math.PI * 2, ((b.max_lon - b.min_lon) / 360) * Math.PI * 2,
    ((90 - b.max_lat) / 180) * Math.PI, ((b.max_lat - b.min_lat) / 180) * Math.PI,
  );

/** Pick 4k textures on capable desktops, 2k on phones / small GPUs. */
const chooseTier = (renderer: THREE.WebGLRenderer) => {
  const small = Math.min(window.innerWidth, window.innerHeight) < 700 || /Mobi|Android|iPhone|iPad/i.test(navigator.userAgent);
  return !small && renderer.capabilities.maxTextureSize >= 4096 ? '4k' : '2k';
};

export const EarthGlobe = forwardRef<GlobeHandle, Props>(function EarthGlobe(props, ref) {
  const containerRef = useRef<HTMLDivElement>(null);
  const labelRef = useRef<HTMLDivElement | null>(null);
  const propsRef = useRef(props);
  propsRef.current = props;

  const api = useRef<{
    camera: THREE.PerspectiveCamera;
    overlayMesh: THREE.Mesh;
    overlayTexture: THREE.CanvasTexture | null;
    markerGroup: THREE.Group;
    regionGroup: THREE.Group;
    graticule: THREE.LineSegments;
    fly: (target: THREE.Vector3, distance: number) => void;
  } | null>(null);

  useImperativeHandle(ref, () => ({
    flyTo: (target, distance) => {
      const a = api.current;
      if (!a) return;
      a.fly(latLonToVector3(target.lat, target.lon), distance ?? Math.min(a.camera.position.length(), 2.2));
    },
    reset: () => {
      const a = api.current;
      if (!a) return;
      a.fly(latLonToVector3(DEFAULT_VIEW.lat, DEFAULT_VIEW.lon), defaultDistance(a.camera.aspect));
    },
    zoomBy: (factor) => {
      const a = api.current;
      if (!a) return;
      const dir = a.camera.position.clone().normalize();
      a.fly(dir, THREE.MathUtils.clamp(a.camera.position.length() * factor, MIN_DIST, MAX_DIST));
    },
  }), []);

  // ---------------------------------------------------------------- scene setup (once)
  useEffect(() => {
    const container = containerRef.current;
    if (!container) return;
    const width = Math.max(1, container.clientWidth);
    const height = Math.max(1, container.clientHeight);

    const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: 'high-performance' });
    const mobile = /Mobi|Android|iPhone|iPad/i.test(navigator.userAgent);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, mobile ? 1.5 : 2));
    renderer.setSize(width, height);
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    container.appendChild(renderer.domElement);
    renderer.domElement.style.touchAction = 'none';
    const tier = chooseTier(renderer);
    const maxAniso = Math.min(8, renderer.capabilities.getMaxAnisotropy());

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(36, width / height, 0.01, 300);
    camera.position.copy(latLonToVector3(DEFAULT_VIEW.lat, DEFAULT_VIEW.lon, defaultDistance(width / height)));
    scene.add(camera);

    // ------------------------------------------------ textures
    const loader = new THREE.TextureLoader();
    const placeholder = new THREE.DataTexture(new Uint8Array([0, 0, 0, 255]), 1, 1);
    placeholder.needsUpdate = true;
    const flatSurface = new THREE.DataTexture(new Uint8Array([128, 128, 255, 255]), 1, 1);
    flatSurface.needsUpdate = true;
    const textures: THREE.Texture[] = [placeholder, flatSurface];
    const load = (url: string, srgb: boolean, onLoad: (t: THREE.Texture) => void) => {
      const t = loader.load(url, (tex) => {
        tex.colorSpace = srgb ? THREE.SRGBColorSpace : THREE.NoColorSpace;
        tex.anisotropy = maxAniso;
        onLoad(tex);
      });
      textures.push(t);
    };

    const sunDir = new THREE.Vector3(1, 0.3, 0.5).normalize();
    const earthUniforms = {
      dayMap: { value: placeholder as THREE.Texture },
      nightMap: { value: placeholder as THREE.Texture },
      cloudMap: { value: placeholder as THREE.Texture },
      surfaceMap: { value: flatSurface as THREE.Texture },
      sunDir: { value: sunDir },
      cloudShift: { value: 0 },
      cloudShadow: { value: 0 },
      reliefStrength: { value: 3.2 },
      nightGain: { value: 1.6 },
      ambient: { value: 0.13 },
    };
    const earthMaterial = new THREE.ShaderMaterial({ uniforms: earthUniforms, vertexShader: earthVertex, fragmentShader: earthFragment });
    const earth = new THREE.Mesh(new THREE.SphereGeometry(1, 160, 80), earthMaterial);
    scene.add(earth);

    // Day map first (it is what the user waits for), then the rest
    load(`/textures/earth-day-${tier}.jpg`, true, (t) => {
      earthUniforms.dayMap.value = t;
      propsRef.current.onReady?.();
      load(`/textures/earth-surface-2k.png`, false, (s) => { earthUniforms.surfaceMap.value = s; });
      load(`/textures/earth-night-${tier}.jpg`, true, (n) => { earthUniforms.nightMap.value = n; });
      load(`/textures/earth-clouds-${tier}.jpg`, false, (c) => {
        c.wrapS = THREE.RepeatWrapping; // the drifting cloud lookup wraps across the dateline
        c.needsUpdate = true;
        earthUniforms.cloudMap.value = c;
        cloudUniforms.cloudMap.value = c;
        cloudsReady = true;
      });
    });

    // ------------------------------------------------ clouds
    let cloudsReady = false;
    const cloudUniforms = {
      cloudMap: { value: placeholder as THREE.Texture },
      sunDir: { value: sunDir },
      opacity: { value: 0 },
    };
    const clouds = new THREE.Mesh(
      new THREE.SphereGeometry(1.007, 128, 64),
      new THREE.ShaderMaterial({
        uniforms: cloudUniforms, vertexShader: cloudVertex, fragmentShader: cloudFragment,
        transparent: true, depthWrite: false,
      }),
    );
    scene.add(clouds);

    // ------------------------------------------------ atmosphere glow
    const ATMO_R = 1.028;
    const atmosphere = new THREE.Mesh(
      new THREE.SphereGeometry(ATMO_R, 96, 48),
      new THREE.ShaderMaterial({
        uniforms: { sunDir: { value: sunDir }, innerRim: { value: Math.sqrt(1 - 1 / (ATMO_R * ATMO_R)) } },
        vertexShader: atmosphereVertex, fragmentShader: atmosphereFragment,
        side: THREE.BackSide, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending,
      }),
    );
    scene.add(atmosphere);

    // ------------------------------------------------ optional graticule
    const gratPts: THREE.Vector3[] = [];
    for (let lat = -60; lat <= 60; lat += 30) {
      for (let lon = -180; lon < 180; lon += 3) gratPts.push(latLonToVector3(lat, lon, 1.0025), latLonToVector3(lat, lon + 3, 1.0025));
    }
    for (let lon = -180; lon < 180; lon += 30) {
      for (let lat = -84; lat < 84; lat += 3) gratPts.push(latLonToVector3(lat, lon, 1.0025), latLonToVector3(lat + 3, lon, 1.0025));
    }
    const graticule = new THREE.LineSegments(
      new THREE.BufferGeometry().setFromPoints(gratPts),
      new THREE.LineBasicMaterial({ color: 0xbfefff, transparent: true, opacity: 0.16, depthWrite: false }),
    );
    graticule.visible = propsRef.current.showGrid;
    scene.add(graticule);

    // ------------------------------------------------ stars: faint, varied, no glow
    const starCount = 2600;
    const starPos = new Float32Array(starCount * 3);
    const starCol = new Float32Array(starCount * 3);
    const tint = [new THREE.Color(0xffffff), new THREE.Color(0xcad8ff), new THREE.Color(0xffe9c4)];
    for (let i = 0; i < starCount; i++) {
      const v = new THREE.Vector3().randomDirection().multiplyScalar(120);
      starPos.set([v.x, v.y, v.z], i * 3);
      const b = Math.pow(Math.random(), 2.4) * 0.85 + 0.08;
      const c = tint[i % 3].clone().multiplyScalar(b);
      starCol.set([c.r, c.g, c.b], i * 3);
    }
    const starGeom = new THREE.BufferGeometry();
    starGeom.setAttribute('position', new THREE.BufferAttribute(starPos, 3));
    starGeom.setAttribute('color', new THREE.BufferAttribute(starCol, 3));
    const stars = new THREE.Points(starGeom, new THREE.PointsMaterial({ size: 1.4, sizeAttenuation: false, vertexColors: true, depthWrite: false }));
    scene.add(stars);

    // ------------------------------------------------ data overlay shell
    const overlayUniforms = { map: { value: placeholder as THREE.Texture }, opacity: { value: 0.92 } };
    const overlayMesh = new THREE.Mesh(
      new THREE.SphereGeometry(1.004, 160, 80),
      new THREE.ShaderMaterial({
        uniforms: overlayUniforms, vertexShader: overlayVertex, fragmentShader: overlayFragment,
        transparent: true, depthWrite: false,
      }),
    );
    overlayMesh.visible = false;
    scene.add(overlayMesh);

    const markerGroup = new THREE.Group();
    const regionGroup = new THREE.Group();
    const draftGroup = new THREE.Group();
    scene.add(markerGroup, regionGroup, draftGroup);

    // HTML label for the selected place (positioned every frame, no React re-render)
    const labelEl = document.createElement('div');
    labelEl.className = 'globe-label';
    labelEl.setAttribute('aria-hidden', 'true');
    container.appendChild(labelEl);
    labelRef.current = labelEl;

    // ------------------------------------------------ controls
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.07;
    controls.enablePan = false;
    controls.minDistance = MIN_DIST;
    controls.maxDistance = MAX_DIST;
    controls.zoomSpeed = 0.7;
    controls.autoRotateSpeed = -0.28; // negative = Earth appears to turn eastward, like the real one
    let lastInteraction = 0;
    controls.addEventListener('start', () => { lastInteraction = performance.now(); });
    controls.addEventListener('end', () => { lastInteraction = performance.now(); });

    // Fly-to animation: slerp the direction, ease the distance, and for long trips rise
    // above the planet mid-flight (like Google Earth) so the motion reads as travel.
    let flight: { from: THREE.Vector3; to: THREE.Vector3; d0: number; d1: number; t0: number; ms: number; arc: number } | null = null;
    const fly = (target: THREE.Vector3, distance: number) => {
      lastInteraction = performance.now();
      const from = camera.position.clone().normalize();
      const to = target.clone().normalize();
      const angle = from.angleTo(to); // radians, 0..pi
      const d0 = camera.position.length();
      const d1 = THREE.MathUtils.clamp(distance, MIN_DIST, MAX_DIST);
      flight = {
        from, to, d0, d1,
        t0: performance.now(),
        ms: THREE.MathUtils.clamp(1000 + angle * 650, 1100, 2600),
        arc: angle > 0.6 ? Math.max(0, Math.min(3.2, 1.1 + angle * 0.8) - Math.max(d0, d1)) : 0,
      };
    };
    api.current = { camera, overlayMesh, overlayTexture: null, markerGroup, regionGroup, graticule, fly };

    // ------------------------------------------------ picking
    const raycaster = new THREE.Raycaster();
    const ndc = new THREE.Vector2();
    const unitSphere = new THREE.Sphere(new THREE.Vector3(), 1);
    const hit = new THREE.Vector3();
    const pick = (clientX: number, clientY: number): LatLon | null => {
      const rect = renderer.domElement.getBoundingClientRect();
      ndc.set(((clientX - rect.left) / rect.width) * 2 - 1, -((clientY - rect.top) / rect.height) * 2 + 1);
      camera.updateMatrixWorld();
      raycaster.setFromCamera(ndc, camera);
      return raycaster.ray.intersectSphere(unitSphere, hit) ? vector3ToLatLon(hit) : null;
    };

    const drawDraft = (box: BBox | null) => {
      draftGroup.clear();
      if (!box) return;
      draftGroup.add(new THREE.Line(
        new THREE.BufferGeometry().setFromPoints(boxOutline(box, 1.009)),
        new THREE.LineBasicMaterial({ color: 0xffffff, transparent: true, opacity: 0.9 }),
      ));
    };

    let down: { x: number; y: number } | null = null;
    let dragStart: LatLon | null = null;
    let draftBox: BBox | null = null;
    let hoverFrame = 0;

    const onPointerDown = (e: PointerEvent) => {
      flight = null;
      lastInteraction = performance.now();
      down = { x: e.clientX, y: e.clientY };
      if (propsRef.current.drawMode) {
        const p = pick(e.clientX, e.clientY);
        if (p) {
          dragStart = p;
          controls.enabled = false;
          renderer.domElement.setPointerCapture(e.pointerId);
        }
      }
    };
    const onPointerMove = (e: PointerEvent) => {
      if (dragStart) {
        const p = pick(e.clientX, e.clientY);
        if (p) {
          draftBox = boxFromCorners(dragStart, p);
          drawDraft(draftBox);
        }
      }
      if (propsRef.current.onHover && !hoverFrame) {
        const { clientX, clientY } = e;
        hoverFrame = requestAnimationFrame(() => {
          hoverFrame = 0;
          propsRef.current.onHover?.(pick(clientX, clientY));
        });
      }
    };
    const onPointerUp = (e: PointerEvent) => {
      lastInteraction = performance.now();
      if (dragStart) {
        const box = draftBox;
        dragStart = null;
        draftBox = null;
        drawDraft(null);
        controls.enabled = true;
        if (box && box.max_lat - box.min_lat > 0.3 && box.max_lon - box.min_lon > 0.3) propsRef.current.onRegion(box);
        down = null;
        return;
      }
      if (down && Math.hypot(e.clientX - down.x, e.clientY - down.y) < 5) {
        const p = pick(e.clientX, e.clientY);
        if (p) propsRef.current.onPick(p);
      }
      down = null;
    };
    const onWheel = () => { lastInteraction = performance.now(); flight = null; };
    const onLeave = () => propsRef.current.onHover?.(null);
    const el = renderer.domElement;
    el.addEventListener('pointerdown', onPointerDown);
    el.addEventListener('pointermove', onPointerMove);
    el.addEventListener('pointerup', onPointerUp);
    el.addEventListener('pointerleave', onLeave);
    el.addEventListener('wheel', onWheel, { passive: true });

    const resize = () => {
      const w = Math.max(1, container.clientWidth);
      const h = Math.max(1, container.clientHeight);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      renderer.setSize(w, h);
    };
    const observer = new ResizeObserver(resize);
    observer.observe(container);

    // ------------------------------------------------ sun
    const camRight = new THREE.Vector3();
    const camUp = new THREE.Vector3();
    const camBack = new THREE.Vector3();
    let realSun = new THREE.Vector3();
    let realSunAt = 0;
    const updateSun = (now: number) => {
      if (propsRef.current.sunMode === 'real') {
        if (now - realSunAt > 30000) { // once every 30 s is plenty
          const s = subsolarPoint(new Date());
          realSun = latLonToVector3(s.lat, s.lon).normalize();
          realSunAt = now;
        }
        sunDir.copy(realSun);
      } else {
        // Sun above-left of the viewer: the visible face is lit, the terminator shows on the right limb
        camera.matrixWorld.extractBasis(camRight, camUp, camBack);
        sunDir.copy(camBack).multiplyScalar(0.72).addScaledVector(camRight, -0.6).addScaledVector(camUp, 0.36).normalize();
      }
    };

    // ------------------------------------------------ render loop
    let frame = 0;
    let last = performance.now();
    let fpsFrames = 0;
    let fpsAt = last;
    let cloudOpacity = 0;
    const animate = () => {
      frame = requestAnimationFrame(animate);
      const now = performance.now();
      const dt = Math.min(0.1, (now - last) / 1000);
      last = now;

      if (flight) {
        const k = Math.min(1, (now - flight.t0) / flight.ms);
        const e = k < 0.5 ? 4 * k * k * k : 1 - Math.pow(-2 * k + 2, 3) / 2;
        const q = new THREE.Quaternion().setFromUnitVectors(flight.from, flight.to);
        const dir = flight.from.clone().applyQuaternion(new THREE.Quaternion().slerp(q, e));
        const lift = flight.arc * Math.sin(Math.PI * Math.min(1, k * 1.05));
        camera.position.copy(dir.multiplyScalar(THREE.MathUtils.lerp(flight.d0, flight.d1, e) + lift));
        camera.lookAt(0, 0, 0);
        if (k >= 1) flight = null;
      }
      const dist = camera.position.length();
      controls.rotateSpeed = 0.12 + 0.45 * ((dist - MIN_DIST) / (MAX_DIST - MIN_DIST));
      const idle = now - lastInteraction > IDLE_BEFORE_SPIN_MS;
      controls.autoRotate = propsRef.current.autoRotate && idle && !flight && !dragStart;
      if (!flight) controls.update();

      // Axial tilt: full 23.4° when viewing the whole planet, north-up when zoomed in
      camera.rotateZ(AXIAL_TILT * THREE.MathUtils.smoothstep(dist, 1.7, 3.0));
      camera.updateMatrixWorld();
      updateSun(now);

      // Clouds drift independently and fade in/out smoothly
      clouds.rotation.y += CLOUD_SPEED * dt;
      earthUniforms.cloudShift.value = clouds.rotation.y / (Math.PI * 2);
      const targetOpacity = propsRef.current.clouds && cloudsReady ? 0.8 : 0;
      cloudOpacity += (targetOpacity - cloudOpacity) * Math.min(1, dt * 4);
      cloudUniforms.opacity.value = cloudOpacity;
      earthUniforms.cloudShadow.value = cloudOpacity * 0.38;
      clouds.visible = cloudOpacity > 0.01;
      // Zoomed in, clouds thin out so the ground stays visible
      cloudUniforms.opacity.value *= 0.55 + 0.45 * THREE.MathUtils.smoothstep(dist, 1.3, 2.2);

      // Place label: project to the screen; fade out when the point turns away
      const lab = propsRef.current.label;
      if (lab && labelEl.textContent) {
        const p = latLonToVector3(lab.lat, lab.lon, 1.01);
        const facing = p.clone().normalize().dot(camera.position.clone().sub(p).normalize());
        p.project(camera);
        const w = container.clientWidth;
        const h = container.clientHeight;
        labelEl.style.transform = `translate(${((p.x + 1) / 2) * w}px, ${((1 - p.y) / 2) * h}px)`;
        labelEl.style.opacity = String(THREE.MathUtils.smoothstep(facing, 0.05, 0.25));
      } else {
        labelEl.style.opacity = '0';
      }

      const ring = markerGroup.getObjectByName('pulse');
      if (ring) {
        const t = (now / 1000) * 0.9;
        ring.scale.setScalar(1 + (t % 1) * 1.8);
        ((ring as THREE.Mesh).material as THREE.MeshBasicMaterial).opacity = 0.7 * (1 - (t % 1));
      }
      renderer.render(scene, camera);

      fpsFrames++;
      if (now - fpsAt > 2000) {
        propsRef.current.onStats?.({ fps: Math.round((fpsFrames * 1000) / (now - fpsAt)), tier });
        fpsFrames = 0;
        fpsAt = now;
      }
    };
    animate();

    return () => {
      cancelAnimationFrame(frame);
      if (hoverFrame) cancelAnimationFrame(hoverFrame);
      observer.disconnect();
      el.removeEventListener('pointerdown', onPointerDown);
      el.removeEventListener('pointermove', onPointerMove);
      el.removeEventListener('pointerup', onPointerUp);
      el.removeEventListener('pointerleave', onLeave);
      el.removeEventListener('wheel', onWheel);
      controls.dispose();
      scene.traverse((obj) => {
        const m = obj as THREE.Mesh;
        m.geometry?.dispose?.();
        const mat = m.material as THREE.Material | THREE.Material[] | undefined;
        (Array.isArray(mat) ? mat : mat ? [mat] : []).forEach((x) => x.dispose());
      });
      textures.forEach((t) => t.dispose());
      api.current?.overlayTexture?.dispose();
      renderer.dispose();
      container.removeChild(renderer.domElement);
      container.removeChild(labelEl);
      labelRef.current = null;
      api.current = null;
    };
  }, []);

  // ---------------------------------------------------------------- marker
  useEffect(() => {
    const a = api.current;
    if (!a) return;
    a.markerGroup.clear();
    if (!props.marker) return;
    const p = latLonToVector3(props.marker.lat, props.marker.lon, 1.0095);
    const dot = new THREE.Mesh(new THREE.SphereGeometry(0.0055, 16, 12), new THREE.MeshBasicMaterial({ color: 0xffffff }));
    dot.position.copy(p);
    const halo = new THREE.Mesh(
      new THREE.RingGeometry(0.009, 0.0125, 40),
      new THREE.MeshBasicMaterial({ color: 0x5ff3ff, transparent: true, opacity: 0.95, side: THREE.DoubleSide, depthWrite: false }),
    );
    const pulse = new THREE.Mesh(
      new THREE.RingGeometry(0.012, 0.014, 40),
      new THREE.MeshBasicMaterial({ color: 0x5ff3ff, transparent: true, opacity: 0.7, side: THREE.DoubleSide, depthWrite: false }),
    );
    pulse.name = 'pulse';
    for (const ring of [halo, pulse]) {
      ring.position.copy(p);
      ring.lookAt(p.clone().multiplyScalar(2));
    }
    a.markerGroup.add(dot, halo, pulse);
  }, [props.marker?.lat, props.marker?.lon]);

  // ---------------------------------------------------------------- region
  const r = props.region;
  useEffect(() => {
    const a = api.current;
    if (!a) return;
    a.regionGroup.clear();
    if (!r) return;
    a.regionGroup.add(
      new THREE.Mesh(
        boxPatch(r, 1.0085),
        new THREE.MeshBasicMaterial({ color: 0x3fe0ff, transparent: true, opacity: 0.14, depthWrite: false, side: THREE.DoubleSide }),
      ),
      new THREE.Line(
        new THREE.BufferGeometry().setFromPoints(boxOutline(r, 1.009)),
        new THREE.LineBasicMaterial({ color: 0x7ff3ff, transparent: true, opacity: 0.95 }),
      ),
    );
  }, [r?.min_lat, r?.max_lat, r?.min_lon, r?.max_lon]);

  // ---------------------------------------------------------------- data overlay
  useEffect(() => {
    const a = api.current;
    if (!a) return;
    const mat = a.overlayMesh.material as THREE.ShaderMaterial;
    if (!props.overlay) {
      a.overlayMesh.visible = false;
      return;
    }
    if (!a.overlayTexture || a.overlayTexture.image !== props.overlay) {
      a.overlayTexture?.dispose();
      const tex = new THREE.CanvasTexture(props.overlay);
      tex.colorSpace = THREE.SRGBColorSpace;
      tex.magFilter = THREE.LinearFilter;
      tex.minFilter = THREE.LinearFilter;
      tex.generateMipmaps = false;
      tex.wrapS = THREE.RepeatWrapping; // no seam at the dateline
      a.overlayTexture = tex;
      mat.uniforms.map.value = tex;
    }
    a.overlayTexture.needsUpdate = true;
    a.overlayMesh.visible = true;
  }, [props.overlay, props.overlayVersion]);

  useEffect(() => {
    if (api.current) api.current.graticule.visible = props.showGrid;
  }, [props.showGrid]);

  useEffect(() => {
    if (labelRef.current) labelRef.current.textContent = props.label?.text ?? '';
  }, [props.label?.text]);

  useEffect(() => {
    if (containerRef.current) containerRef.current.style.cursor = props.drawMode ? 'crosshair' : 'grab';
  }, [props.drawMode]);

  return <div ref={containerRef} className="earth-globe" />;
});

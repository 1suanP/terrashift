/**
 * GLSL for the realistic Earth: surface, clouds, atmosphere, and data overlay.
 * All lighting is done in world space with a single directional sun.
 * Textures are sampled linear (sRGB maps are decoded by WebGL), and the final colour
 * goes through three.js' output colour-space conversion.
 */

const commonVertex = /* glsl */ `
  varying vec2 vUv;
  varying vec3 vNormalW;
  varying vec3 vPosW;
  void main() {
    vUv = uv;
    vNormalW = normalize(mat3(modelMatrix) * normal);
    vec4 wp = modelMatrix * vec4(position, 1.0);
    vPosW = wp.xyz;
    gl_Position = projectionMatrix * viewMatrix * wp;
  }
`;

export const earthVertex = commonVertex;

export const earthFragment = /* glsl */ `
  uniform sampler2D dayMap;
  uniform sampler2D nightMap;
  uniform sampler2D cloudMap;
  uniform sampler2D surfaceMap;   // rg = normal xy (DirectX: green flipped), b = water mask
  uniform vec3 sunDir;
  uniform float cloudShift;       // cloud layer rotation / (2*pi)
  uniform float cloudShadow;      // 0 when clouds are hidden
  uniform float reliefStrength;
  uniform float nightGain;
  uniform float ambient;
  varying vec2 vUv;
  varying vec3 vNormalW;
  varying vec3 vPosW;

  void main() {
    vec3 N = normalize(vNormalW);
    vec3 V = normalize(cameraPosition - vPosW);
    vec3 east = normalize(cross(vec3(0.0, 1.0, 0.0), N) + vec3(1e-6, 0.0, 0.0));
    vec3 north = cross(N, east);

    vec4 surf = texture2D(surfaceMap, vUv);
    float water = smoothstep(0.35, 0.65, surf.b);
    vec2 nxy = surf.rg * 2.0 - 1.0;
    vec3 Np = normalize(N + reliefStrength * (nxy.x * east - nxy.y * north) * (1.0 - water));

    float sunGeo = dot(N, sunDir);
    float dayMix = smoothstep(-0.10, 0.22, sunGeo);
    float diffuse = max(dot(Np, sunDir), 0.0);

    // Cloud shadows: sample the cloud layer slightly toward the sun
    vec2 sunEN = vec2(dot(sunDir, east), dot(sunDir, north));
    // (cloud texture uses RepeatWrapping, so no fract() and no seam)
    vec2 cuv = vec2(vUv.x - cloudShift + sunEN.x * 0.0018, clamp(vUv.y + sunEN.y * 0.0036, 0.0, 1.0));
    float cloud = texture2D(cloudMap, cuv).r;
    float shadow = 1.0 - cloudShadow * cloud * smoothstep(0.0, 0.3, sunGeo);

    vec3 day = texture2D(dayMap, vUv).rgb;
    vec3 lit = day * (ambient + (1.0 - ambient) * diffuse * 1.12) * shadow;

    // Sun glint on open water (sharp highlight + broad sheen)
    vec3 H = normalize(sunDir + V);
    float nh = max(dot(N, H), 0.0);
    float glint = (pow(nh, 220.0) * 0.32 + pow(nh, 14.0) * 0.035) * water;
    lit += vec3(1.0, 0.96, 0.88) * glint * smoothstep(0.0, 0.25, sunGeo) * shadow;

    // City lights on the night side, dimmed under clouds
    vec3 lights = texture2D(nightMap, vUv).rgb * nightGain * (1.0 - 0.75 * cloudShadow * cloud);
    vec3 nightSide = lights + day * 0.015;

    vec3 col = mix(nightSide, lit, dayMix);

    // Thin blue scattering toward the limb on the lit side
    float limb = pow(1.0 - max(dot(N, V), 0.0), 3.0);
    vec3 sky = vec3(0.30, 0.56, 1.0);
    col = mix(col, sky * (0.35 + 0.65 * dayMix), limb * 0.6 * smoothstep(-0.2, 0.5, sunGeo));
    // A faint reddish band right at the terminator
    float tg = sunGeo * 9.0; // (pow() is undefined for negative bases in GLSL)
    col += vec3(0.28, 0.10, 0.03) * day * exp(-tg * tg) * 0.6;

    gl_FragColor = vec4(col, 1.0);
    #include <tonemapping_fragment>
    #include <colorspace_fragment>
  }
`;

export const cloudVertex = commonVertex;

export const cloudFragment = /* glsl */ `
  uniform sampler2D cloudMap;
  uniform vec3 sunDir;
  uniform float opacity;
  varying vec2 vUv;
  varying vec3 vNormalW;
  varying vec3 vPosW;
  void main() {
    // drop thin haze and keep only defined cloud systems
    float c = smoothstep(0.10, 0.88, texture2D(cloudMap, vUv).r);
    vec3 N = normalize(vNormalW);
    vec3 V = normalize(cameraPosition - vPosW);
    float d = dot(N, sunDir);
    float lightAmt = smoothstep(-0.12, 0.35, d);
    vec3 col = mix(vec3(0.03, 0.035, 0.05), vec3(1.0, 0.985, 0.96), lightAmt * (0.45 + 0.55 * max(d, 0.0)));
    // slightly thicker-looking toward the limb, but never a solid white rim
    float limb = 1.0 + 0.35 * pow(1.0 - max(dot(N, V), 0.0), 2.0);
    float alpha = clamp(c * opacity * limb, 0.0, 0.95) * (0.35 + 0.65 * lightAmt);
    gl_FragColor = vec4(col, alpha);
    #include <colorspace_fragment>
  }
`;

export const atmosphereVertex = commonVertex;

export const atmosphereFragment = /* glsl */ `
  uniform vec3 sunDir;
  uniform float innerRim;   // -dot(n, v) at Earth's limb for this shell radius
  varying vec2 vUv;
  varying vec3 vNormalW;
  varying vec3 vPosW;
  void main() {
    vec3 N = normalize(vNormalW);
    vec3 V = normalize(cameraPosition - vPosW);
    float r = clamp(-dot(N, V) / innerRim, 0.0, 1.0);     // 1 at Earth's limb, 0 at the shell edge
    float glow = pow(r, 2.2);
    float dayF = smoothstep(-0.35, 0.45, dot(N, sunDir));
    vec3 col = mix(vec3(0.20, 0.42, 1.0), vec3(0.45, 0.72, 1.0), glow);
    // additive blending: colour is added as-is (alpha 1 avoids attenuating twice)
    gl_FragColor = vec4(col * glow * (0.12 + 0.88 * dayF) * 0.9, 1.0);
    #include <colorspace_fragment>
  }
`;

export const overlayVertex = commonVertex;

export const overlayFragment = /* glsl */ `
  uniform sampler2D map;
  uniform float opacity;
  varying vec2 vUv;
  varying vec3 vNormalW;
  varying vec3 vPosW;
  void main() {
    vec4 c = texture2D(map, vUv);
    vec3 N = normalize(vNormalW);
    vec3 V = normalize(cameraPosition - vPosW);
    float shade = 0.78 + 0.22 * max(dot(N, V), 0.0);   // gentle limb darkening only; data stays readable at night
    gl_FragColor = vec4(c.rgb * shade, c.a * opacity);
    #include <colorspace_fragment>
  }
`;

/** Approximate sub-solar point for a date (±1°): declination and longitude. */
export const subsolarPoint = (date: Date) => {
  const start = Date.UTC(date.getUTCFullYear(), 0, 0);
  const dayOfYear = (date.getTime() - start) / 86400000;
  const decl = -23.44 * Math.cos(((2 * Math.PI) / 365) * (dayOfYear + 10));
  const hours = date.getUTCHours() + date.getUTCMinutes() / 60 + date.getUTCSeconds() / 3600;
  // equation of time (minutes), NOAA approximation
  const g = ((2 * Math.PI) / 365) * (dayOfYear - 1 + (hours - 12) / 24);
  const eot = 229.18 * (0.000075 + 0.001868 * Math.cos(g) - 0.032077 * Math.sin(g) - 0.014615 * Math.cos(2 * g) - 0.040849 * Math.sin(2 * g));
  const lon = -15 * (hours - 12 + eot / 60);
  return { lat: decl, lon: ((lon + 540) % 360) - 180 };
};

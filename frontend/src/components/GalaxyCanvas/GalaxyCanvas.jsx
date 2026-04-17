import React, { useMemo, useState, useEffect, useRef, useLayoutEffect } from 'react';
import { Canvas, useThree } from '@react-three/fiber';
import { OrbitControls } from '@react-three/drei';
import * as THREE from 'three';

import { rgb01FromValenceEnergy } from '../../services/tracksApi';
import { logGalaxyGeometry } from '../../utils/mapPerf';

function hexToRgb01(hex) {
  if (!hex || typeof hex !== 'string') return null;
  let h = hex.replace('#', '').trim();
  if (h.length === 3) {
    h = h[0] + h[0] + h[1] + h[1] + h[2] + h[2];
  }
  if (h.length !== 6 || !/^[0-9a-fA-F]{6}$/.test(h)) return null;
  return [
    parseInt(h.slice(0, 2), 16) / 255,
    parseInt(h.slice(2, 4), 16) / 255,
    parseInt(h.slice(4, 6), 16) / 255,
  ];
}

/**
 * Resolve per-point RGB like the old Sprite path: hex, THREE.Color-like, number, or valence/energy.
 * (Previously hexToRgb01 only accepted strings — non-strings made every point the same gray.)
 */
function pointToRgb01(p) {
  const c = p.color;
  if (typeof c === 'string') {
    const rgb = hexToRgb01(c);
    if (rgb) return rgb;
  }
  if (c && typeof c === 'object') {
    if (typeof c.r === 'number' && typeof c.g === 'number' && typeof c.b === 'number') {
      return [c.r, c.g, c.b];
    }
  }
  if (typeof c === 'number' && Number.isFinite(c)) {
    const hex = (c & 0xffffff).toString(16).padStart(6, '0');
    const rgb = hexToRgb01(`#${hex}`);
    if (rgb) return rgb;
  }
  return rgb01FromValenceEnergy(p.valence, p.energy);
}

/**
 * Один THREE.Points: без фильтра все точки «полные»; с фильтром — слой фона мельче/тусклее,
 * совпадения поверх (крупнее и ярче).
 */
function GalaxyPointsCloud({
  points,
  emphasizedTrackIds,
  onPointClick,
  setHoveredPoint,
  timerRef,
  starTexture,
}) {
  const { raycaster } = useThree();

  useLayoutEffect(() => {
    const t = raycaster.params.Points;
    if (t) t.threshold = 0.5;
  }, [raycaster]);

  const layers = useMemo(() => {
    const emphasize =
      emphasizedTrackIds != null && typeof emphasizedTrackIds.has === 'function';

    const back = [];
    const front = [];
    if (!emphasize) {
      for (let i = 0; i < points.length; i++) front.push(points[i]);
    } else {
      for (let i = 0; i < points.length; i++) {
        const p = points[i];
        if (emphasizedTrackIds.has(p.track_id)) front.push(p);
        else back.push(p);
      }
    }

    const buildGeo = (list, colorMul) => {
      const t0 = performance.now();
      const n = list.length;
      if (n === 0) return null;
      const positions = new Float32Array(n * 3);
      const colors = new Float32Array(n * 3);
      for (let i = 0; i < n; i++) {
        const p = list[i];
        const j = i * 3;
        positions[j] = p.x;
        positions[j + 1] = p.y;
        positions[j + 2] = p.z ?? 0;
        const [r, g, b] = pointToRgb01(p);
        colors[j] = r * colorMul;
        colors[j + 1] = g * colorMul;
        colors[j + 2] = b * colorMul;
      }
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
      geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
      geo.computeBoundingSphere();
      logGalaxyGeometry(performance.now() - t0, n);
      return { geo, list };
    };

    if (!emphasize) {
      const g = buildGeo(front, 1);
      return g ? [{ ...g, size: 10 }] : [];
    }

    const out = [];
    const bg = buildGeo(back, 0.22);
    if (bg) out.push({ ...bg, size: 3.2 });
    const fg = buildGeo(front, 1);
    if (fg) out.push({ ...fg, size: 10 });
    return out;
  }, [points, emphasizedTrackIds]);

  useLayoutEffect(() => {
    return () => {
      for (const L of layers) {
        if (L?.geo) L.geo.dispose();
      }
    };
  }, [layers]);

  const handlePointerOut = () => {
    document.body.style.cursor = 'default';
    if (timerRef.current) clearTimeout(timerRef.current);
    setHoveredPoint(null);
  };

  if (layers.length === 0) {
    return null;
  }

  return (
    <>
      {layers.map((layer, layerIdx) => (
        <points
          key={layerIdx}
          renderOrder={layerIdx}
          geometry={layer.geo}
          frustumCulled
          onClick={(e) => {
            e.stopPropagation();
            const idx = e.index;
            const list = layer.list;
            if (idx == null || idx < 0 || idx >= list.length) return;
            onPointClick(list[idx].track_id);
          }}
          onPointerMove={(e) => {
            e.stopPropagation();
            const idx = e.index;
            const list = layer.list;
            if (idx != null && idx >= 0 && idx < list.length) {
              document.body.style.cursor = 'pointer';
              if (timerRef.current) clearTimeout(timerRef.current);
              timerRef.current = setTimeout(() => {
                setHoveredPoint(list[idx]);
              }, 400);
            } else {
              handlePointerOut();
            }
          }}
          onPointerOut={handlePointerOut}
        >
          <pointsMaterial
            map={starTexture}
            vertexColors
            toneMapped={false}
            transparent
            opacity={1}
            size={layer.size}
            sizeAttenuation
            depthWrite={false}
            depthTest
            blending={THREE.AdditiveBlending}
          />
        </points>
      ))}
    </>
  );
}

export default function GalaxyCanvas({ points, emphasizedTrackIds, onPointClick }) {
  const [hoveredPoint, setHoveredPoint] = useState(null);
  const [mousePos, setMousePos] = useState({ x: 0, y: 0 });
  const timerRef = useRef(null);

  const starTexture = useMemo(() => {
    const canvas = document.createElement('canvas');
    canvas.width = 128;
    canvas.height = 128;
    const context = canvas.getContext('2d');
    const gradient = context.createRadialGradient(64, 64, 0, 64, 64, 64);

    gradient.addColorStop(0, 'rgba(255, 255, 255, 1)');
    gradient.addColorStop(0.12, 'rgba(255, 255, 255, 0.95)');
    gradient.addColorStop(0.35, 'rgba(255, 255, 255, 0.45)');
    gradient.addColorStop(0.65, 'rgba(255, 255, 255, 0.12)');
    gradient.addColorStop(1, 'rgba(255, 255, 255, 0)');

    context.fillStyle = gradient;
    context.fillRect(0, 0, 128, 128);

    const texture = new THREE.CanvasTexture(canvas);
    return texture;
  }, []);

  useEffect(() => {
    const handleMouseMove = (e) => {
      setMousePos({ x: e.clientX, y: e.clientY });
    };
    window.addEventListener('mousemove', handleMouseMove);
    return () => window.removeEventListener('mousemove', handleMouseMove);
  }, []);

  const showBelow = mousePos.y < 150;
  const showLeft = mousePos.x > window.innerWidth * 0.7;

  return (
    <div style={{ width: '100%', height: '100%', position: 'relative' }}>
      <Canvas camera={{ position: [0, 0, 20], fov: 60 }} style={{ background: '#000' }}>
        <ambientLight intensity={0.5} />
        <OrbitControls enablePan enableZoom enableRotate />

        <GalaxyPointsCloud
          points={points}
          emphasizedTrackIds={emphasizedTrackIds}
          onPointClick={onPointClick}
          setHoveredPoint={setHoveredPoint}
          timerRef={timerRef}
          starTexture={starTexture}
        />
      </Canvas>

      {hoveredPoint && (
        <div
          className="star-tooltip"
          style={{
            position: 'fixed',
            left: showLeft ? mousePos.x - 185 : mousePos.x + 15,
            top: showBelow ? mousePos.y + 100 : mousePos.y,
            pointerEvents: 'none',
          }}
        >
          <strong> title: {hoveredPoint.title}</strong>
          <span>author: {hoveredPoint.artist}</span>
          <small>album: {hoveredPoint.album}</small>
        </div>
      )}
    </div>
  );
}

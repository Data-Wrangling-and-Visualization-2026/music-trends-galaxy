/**
 * Опциональные замеры карты: сеть vs CPU vs первый кадр после данных.
 * Включено в dev или при VITE_PERF_LOG=true в .env
 *
 * Как читать:
 * - Promise.all — время до получения всех ответов и парсинга JSON (сеть + десериализация).
 * - compute pointsWithMetadata — JS-склейка точек с метаданными и цветами (без отрисовки).
 * - galaxy bufferGeometry — заполнение Float32Array + BufferGeometry для THREE.Points.
 * - «до 2-го rAF» — грубая оценка момента после коммита React и композита; включает и Canvas.
 */

const ENABLED = import.meta.env.DEV || import.meta.env.VITE_PERF_LOG === 'true';

function fmt(ms) {
  return `${ms.toFixed(1)}ms`;
}

export function perfMapEnabled() {
  return ENABLED;
}

/** Сеть + JSON.parse для одного fetch (или общий блок). */
export function logMapFetch(label, ms, extra = {}) {
  if (!ENABLED) return;
  console.info(`[map-perf] ${label}: ${fmt(ms)}`, extra);
}

/** Тяжёлый useMemo (например pointsWithMetadata). */
export function logMapCompute(label, ms, extra = {}) {
  if (!ENABLED) return;
  console.info(`[map-perf] compute ${label}: ${fmt(ms)}`, extra);
}

/** Сборка BufferGeometry / точки в Three.js. */
export function logGalaxyGeometry(ms, pointCount) {
  if (!ENABLED) return;
  console.info(`[map-perf] galaxy bufferGeometry: ${fmt(ms)}`, { pointCount });
}

/**
 * Время от старта загрузки до второго rAF после setState — грубая оценка
 * «React commit + Three отрисовка + композит браузера», без чистой изоляции GPU.
 */
export function logMapFirstFrames(msFromLoadStart) {
  if (!ENABLED) return;
  console.info(
    `[map-perf] до 2-го animation frame после ответа (≈отрисовка): ${fmt(msFromLoadStart)}`
  );
}

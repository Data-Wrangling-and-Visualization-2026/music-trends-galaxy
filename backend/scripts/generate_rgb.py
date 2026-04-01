"""
Derive a display hex color from valence and energy in [0, 1].

Uses HSL with a wide hue sweep and strong saturation so tracks look more distinct
on the map. Kept in sync with `rgb01FromValenceEnergy` / `rgbFromValenceEnergy`
in ``frontend/src/services/tracksApi.js``.

Cluster rows use :func:`rgb_for_cluster_metrics` for a **distinct** color per
``code`` (hash-based; aggregate metrics are not used).
"""

import hashlib

def _clip01(x) -> float:
    if x is None:
        return 0.5
    try:
        v = float(x)
    except (TypeError, ValueError):
        return 0.5
    return max(0.0, min(1.0, v))


def _hsl_to_rgb(h: float, s: float, l: float) -> tuple[int, int, int]:
    h = h % 360 / 360.0
    if s == 0:
        x = int(round(l * 255))
        return x, x, x

    def hue2rgb(p: float, q: float, t: float) -> float:
        if t < 0:
            t += 1
        if t > 1:
            t -= 1
        if t < 1 / 6:
            return p + (q - p) * 6 * t
        if t < 1 / 2:
            return q
        if t < 2 / 3:
            return p + (q - p) * (2 / 3 - t) * 6
        return p

    q = l * (1 + s) if l < 0.5 else l + s - l * s
    p = 2 * l - q
    r = hue2rgb(p, q, h + 1 / 3)
    g = hue2rgb(p, q, h)
    b = hue2rgb(p, q, h - 1 / 3)
    return (
        int(round(max(0, min(255, r * 255)))),
        int(round(max(0, min(255, g * 255)))),
        int(round(max(0, min(255, b * 255)))),
    )


def _valence_energy_to_hsl(v: float, e: float) -> tuple[float, float, float]:
    hue = (v * 312 + e * 108 + 180 * v * (1 - e) + 90 * e * (1 - v)) % 360
    sat = min(1.0, max(0.0, 0.62 + 0.36 * abs(v - e)))
    light = min(1.0, max(0.0, 0.4 + 0.28 * (0.35 + 0.65 * e) * (0.5 + 0.5 * v)))
    return hue, sat, light


def rgb_from_valence_energy(valence, energy) -> str:
    v = _clip01(valence)
    e = _clip01(energy)
    h, s, l = _valence_energy_to_hsl(v, e)
    r, g, b = _hsl_to_rgb(h, s, l)
    return f"#{r:02x}{g:02x}{b:02x}"


def rgb_for_cluster_metrics(valence: float | None, energy: float | None, code: str) -> str:
    _ = valence, energy
    key = str(code or "").encode("utf-8")
    d = hashlib.sha256(key).digest()
    hue = (int.from_bytes(d[:4], "big") % 360_000) / 1000.0
    sat = 0.55 + (d[4] / 255.0) * 0.35
    light = 0.38 + (d[5] / 255.0) * 0.22
    r, g, b = _hsl_to_rgb(hue, sat, light)
    return f"#{r:02x}{g:02x}{b:02x}"


def track_color_from_cluster(
    cluster_code: str,
    track_valence,
    track_energy,
    cluster_metrics: dict | None,
) -> str:

    def _rgb_to_hsl(r: int, g: int, b: int) -> tuple[float, float, float]:
        r_, g_, b_ = r / 255.0, g / 255.0, b / 255.0
        mx = max(r_, g_, b_)
        mn = min(r_, g_, b_)
        l = (mx + mn) / 2.0
        if mx == mn:
            return 0.0, 0.0, l
        d = mx - mn
        s = d / (2.0 - mx - mn) if l > 0.5 else d / (mx + mn)
        if mx == r_:
            h = ((g_ - b_) / d) % 6.0
        elif mx == g_:
            h = (b_ - r_) / d + 2.0
        else:
            h = (r_ - g_) / d + 4.0
        h *= 60.0
        if h < 0:
            h += 360.0
        return h, s, l

    def _mean_from_metrics(metrics: dict | None, key: str) -> float | None:
        if not metrics or not isinstance(metrics, dict):
            return None
        block = metrics.get(key)
        if not isinstance(block, dict):
            return None
        m = block.get("mean")
        if m is None:
            return None
        try:
            return float(m)
        except (TypeError, ValueError):
            return None

    cluster_hex = rgb_for_cluster_metrics(None, None, str(cluster_code or ""))

    def _parse_hex_rgb(hx: str) -> tuple[int, int, int]:
        s = (hx or "").strip()
        if s.startswith("#"):
            s = s[1:]
        if len(s) != 6:
            return 128, 128, 128
        try:
            return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)
        except ValueError:
            return 128, 128, 128

    r0, g0, b0 = _parse_hex_rgb(cluster_hex)
    h0, s0, l0 = _rgb_to_hsl(r0, g0, b0)

    mv = _mean_from_metrics(cluster_metrics, "valence")
    me = _mean_from_metrics(cluster_metrics, "energy")
    tv = _clip01(track_valence)
    te = _clip01(track_energy)

    dv = (tv - _clip01(mv)) if mv is not None else 0.0
    de = (te - _clip01(me)) if me is not None else 0.0

    spread = (dv * dv + de * de) ** 0.5
    sqrt2 = 2.0**0.5
    # Stronger response: small metric deltas were nearly invisible (noise_coeff ~0).
    t = min(1.0, spread / sqrt2) if sqrt2 else 0.0
    # Sublinear curve so modest deviations still get visible hue/sat/light shifts.
    noise_coeff = t**0.55 if t > 0 else 0.0
    noise_coeff = min(1.0, noise_coeff * 2.2)

    dh = max(-72.0, min(72.0, dv * 88.0 + de * 58.0))
    ds = max(-0.32, min(0.32, (dv - de) * 0.28))
    dl = max(-0.22, min(0.22, (dv + de) * 0.14))

    dh *= noise_coeff
    ds *= noise_coeff
    dl *= noise_coeff

    h1 = (h0 + dh) % 360.0
    s1 = max(0.0, min(1.0, s0 + ds))
    l1 = max(0.0, min(1.0, l0 + dl))

    r1, g1, b1 = _hsl_to_rgb(h1, s1, l1)
    return f"#{r1:02x}{g1:02x}{b1:02x}"


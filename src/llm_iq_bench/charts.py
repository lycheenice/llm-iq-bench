"""纯 SVG 图表生成（无 matplotlib/numpy 依赖）。

输出：
  - radial 雷达图（多 run 多维度对比）
  - bars 分组柱状图（各任务得分）
  - 单 run 详情柱状图
图片写入 reports/assets/*.svg，在 md 中以 <img> 嵌入，GitHub 可直接渲染。
"""
from __future__ import annotations

import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ASSETS_DIR = ROOT / "reports" / "assets"


def _ensure():
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)


def radial_chart(axes: list[str], series: list[tuple[str, list[float]]],
                 title: str = "", fname: str = "radial.svg",
                 size: int = 360, r_max: float = 1.0) -> Path:
    """雷达图。axes: 维度名列表；series: [(label, [values per axis])]。"""
    _ensure()
    cx = cy = size / 2
    R = size * 0.36
    n = len(axes)
    angles = [(-math.pi / 2 + 2 * math.pi * i / n) for i in range(n)]
    palette = ["#2563eb", "#dc2626", "#16a34a", "#9333ea", "#ea580c", "#0891b2"]

    def pt(i, frac):
        return (cx + R * frac * math.cos(angles[i]), cy + R * frac * math.sin(angles[i]))

    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size+40}" '
             f'viewBox="0 0 {size} {size+40}" font-family="-apple-system,Segoe UI,Roboto,sans-serif">']
    parts.append(f'<text x="{cx}" y="20" text-anchor="middle" font-size="14" font-weight="600" fill="#111">{_esc(title)}</text>')

    # 网格同心多边形
    for g in [0.25, 0.5, 0.75, 1.0]:
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in (pt(i, g) for i in range(n)))
        parts.append(f'<polygon points="{pts}" fill="none" stroke="#e5e7eb" stroke-width="1"/>')
        parts.append(f'<text x="{cx+4:.1f}" y="{cy - R*g:.1f}" font-size="9" fill="#9ca3af">{g*r_max:.2f}</text>')
    # 轴线 + 标签
    for i, ax in enumerate(axes):
        x, y = pt(i, 1.12)
        parts.append(f'<line x1="{cx:.1f}" y1="{cy:.1f}" x2="{pt(i,1)[0]:.1f}" y2="{pt(i,1)[1]:.1f}" stroke="#d1d5db"/>')
        anc = "middle"
        if abs(x - cx) > 30: anc = "start" if x > cx else "end"
        parts.append(f'<text x="{x:.1f}" y="{y:.1f}" text-anchor="{anc}" font-size="11" fill="#374151">{_esc(_short(ax))}</text>')
    # 数据系列
    for si, (label, vals) in enumerate(series):
        color = palette[si % len(palette)]
        pts = []
        for i, v in enumerate(vals):
            frac = min(max(v / r_max, 0), 1.0)
            pts.append(pt(i, frac))
        poly = " ".join(f"{x:.1f},{y:.1f}" for x, y in pts) + f" {pts[0][0]:.1f},{pts[0][1]:.1f}"
        parts.append(f'<polygon points="{poly}" fill="{color}" fill-opacity="0.18" stroke="{color}" stroke-width="2"/>')
        for x, y in pts:
            parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{color}"/>')
    # 图例
    ly = size + 30
    lx = 10
    for si, (label, _) in enumerate(series):
        color = palette[si % len(palette)]
        parts.append(f'<rect x="{lx}" y="{ly-10}" width="12" height="12" fill="{color}"/>')
        parts.append(f'<text x="{lx+16}" y="{ly}" font-size="11" fill="#374151">{_esc(label)}</text>')
        lx += len(label) * 7 + 40
    parts.append("</svg>")
    p = ASSETS_DIR / fname
    p.write_text("\n".join(parts), encoding="utf-8")
    return p


def bars_chart(groups: list[str], series: list[tuple[str, list[float]]],
               title: str = "", fname: str = "bars.svg",
               width: int = 700, height: int = 320, ymax: float = 1.0,
               value_fmt="{:.3f}") -> Path:
    """分组柱状图。groups: x 轴标签；series: [(label, [vals per group])]。"""
    _ensure()
    palette = ["#2563eb", "#dc2626", "#16a34a", "#9333ea", "#ea580c", "#0891b2"]
    ml, mr, mt, mb = 60, 20, 40, 60
    pw = width - ml - mr
    ph = height - mt - mb
    ng = len(groups); ns = len(series)
    gw = pw / ng
    bw = gw * 0.78 / max(ns, 1)
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
             f'viewBox="0 0 {width} {height}" font-family="-apple-system,Segoe UI,Roboto,sans-serif">']
    parts.append(f'<text x="{width/2}" y="20" text-anchor="middle" font-size="14" font-weight="600" fill="#111">{_esc(title)}</text>')
    # y 轴网格
    for g in [0, 0.25, 0.5, 0.75, 1.0]:
        y = mt + ph * (1 - g)
        parts.append(f'<line x1="{ml}" y1="{y:.1f}" x2="{width-mr}" y2="{y:.1f}" stroke="#e5e7eb"/>')
        parts.append(f'<text x="{ml-6}" y="{y+3:.1f}" text-anchor="end" font-size="10" fill="#9ca3af">{g*ymax:.2f}</text>')
    # 柱
    for gi, grp in enumerate(groups):
        x0 = ml + gi * gw + (gw - bw * ns) / 2
        for si, (label, vals) in enumerate(series):
            v = vals[gi] if gi < len(vals) else 0
            h = ph * min(v / ymax, 1.0)
            x = x0 + si * bw
            y = mt + ph - h
            color = palette[si % len(palette)]
            parts.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{bw-2:.1f}" height="{h:.1f}" fill="{color}"/>')
            parts.append(f'<text x="{x+bw/2:.1f}" y="{y-3:.1f}" text-anchor="middle" font-size="9" fill="{color}">{value_fmt.format(v)}</text>')
        parts.append(f'<text x="{ml+gi*gw+gw/2:.1f}" y="{height-mb+18:.1f}" text-anchor="middle" font-size="10" fill="#374151">{_esc(_short(grp))}</text>')
    # 图例
    lx = ml
    ly = height - 14
    for si, (label, _) in enumerate(series):
        color = palette[si % len(palette)]
        parts.append(f'<rect x="{lx}" y="{ly-10}" width="12" height="12" fill="{color}"/>')
        parts.append(f'<text x="{lx+16}" y="{ly}" font-size="11" fill="#374151">{_esc(label)}</text>')
        lx += len(label) * 7 + 40
    parts.append("</svg>")
    p = ASSETS_DIR / fname
    p.write_text("\n".join(parts), encoding="utf-8")
    return p


def hbars_chart(items: list[tuple[str, float]], title: str = "",
                fname: str = "hbars.svg", width: int = 600, height: int = 0,
                ymax: float = 1.0, value_fmt="{:.1%}") -> Path:
    """单系列水平柱状图，items: [(label, value)]，按值降序。"""
    _ensure()
    items = sorted(items, key=lambda x: x[1], reverse=True)
    height = max(160, len(items) * 34 + 40)
    ml, mr, mt, mb = 130, 60, 40, 20
    pw = width - ml - mr
    ph = height - mt - mb
    bh = min(24, ph / max(len(items), 1) * 0.8)
    palette = ["#2563eb", "#16a34a", "#9333ea", "#ea580c", "#dc2626", "#0891b2", "#65a30d", "#4f46e5"]
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
             f'viewBox="0 0 {width} {height}" font-family="-apple-system,Segoe UI,Roboto,sans-serif">']
    parts.append(f'<text x="{width/2}" y="24" text-anchor="middle" font-size="14" font-weight="600" fill="#111">{_esc(title)}</text>')
    for g in [0, 0.5, 1.0]:
        x = ml + pw * g
        parts.append(f'<line x1="{x}" y1="{mt}" x2="{x}" y2="{height-mb}" stroke="#e5e7eb"/>')
        parts.append(f'<text x="{x}" y="{height-mb+14}" text-anchor="middle" font-size="9" fill="#9ca3af">{g*ymax:.2f}</text>')
    for i, (label, v) in enumerate(items):
        y = mt + i * (ph / len(items)) + (ph/len(items) - bh)/2
        w = pw * min(v / ymax, 1.0)
        color = palette[i % len(palette)]
        parts.append(f'<rect x="{ml}" y="{y:.1f}" width="{w:.1f}" height="{bh}" fill="{color}"/>')
        parts.append(f'<text x="{ml-6}" y="{y+bh*0.7:.1f}" text-anchor="end" font-size="11" fill="#374151">{_esc(_short(label))}</text>')
        parts.append(f'<text x="{ml+w+4:.1f}" y="{y+bh*0.7:.1f}" font-size="10" fill="{color}">{value_fmt.format(v)}</text>')
    parts.append("</svg>")
    p = ASSETS_DIR / fname
    p.write_text("\n".join(parts), encoding="utf-8")
    return p


def needle_heatmap(rows: list[tuple[int, float, float]], fname: str = "needle_heat.svg",
                   title: str = "Needle: 长度 × 深度") -> Path:
    """needle 热力图，rows: [(length, depth, score)]。"""
    _ensure()
    lengths = sorted({r[0] for r in rows})
    depths = sorted({r[1] for r in rows})
    cell = 56
    ml, mt = 70, 50
    w = ml + len(lengths) * cell + 10
    h = mt + len(depths) * cell + 30
    grid = {(r[0], r[1]): r[2] for r in rows}
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" '
             f'viewBox="0 0 {w} {h}" font-family="-apple-system,Segoe UI,Roboto,sans-serif">']
    parts.append(f'<text x="{w/2}" y="22" text-anchor="middle" font-size="14" font-weight="600" fill="#111">{_esc(title)}</text>')
    for li, L in enumerate(lengths):
        parts.append(f'<text x="{ml+li*cell+cell/2}" y="{mt-8}" text-anchor="middle" font-size="10" fill="#374151">{L//1000}k</text>')
    for di, d in enumerate(depths):
        parts.append(f'<text x="{ml-6}" y="{mt+di*cell+cell/2+4}" text-anchor="end" font-size="10" fill="#374151">{d:.0%}</text>')
    for li, L in enumerate(lengths):
        for di, d in enumerate(depths):
            v = grid.get((L, d))
            if v is None:
                color, txt = "#f3f4f6", "—"
            else:
                r2 = int(round(255 * (1 - v)))
                color = f"rgb({255},{r2//2+128},{r2//2+128})"
                txt = f"{v:.0%}"
            parts.append(f'<rect x="{ml+li*cell}" y="{mt+di*cell}" width="{cell-2}" height="{cell-2}" fill="{color}" stroke="#fff"/>')
            parts.append(f'<text x="{ml+li*cell+cell/2-1}" y="{mt+di*cell+cell/2+4}" text-anchor="middle" font-size="11" '
                         f'fill="{"#fff" if v and v < 0.5 else "#111"}">{txt}</text>')
    parts.append("</svg>")
    p = ASSETS_DIR / fname
    p.write_text("\n".join(parts), encoding="utf-8")
    return p


def _esc(s: str) -> str:
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _short(name: str) -> str:
    return (name.replace("coding_", "").replace("agent_", "").replace("long_", "")
            .replace("_t02", "(t.2)").replace("_stress", "-s")[:16])

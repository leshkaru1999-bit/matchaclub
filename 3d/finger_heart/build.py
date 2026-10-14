"""Генератор 3D-модели «сердечко из пальцев» (finger heart) для печати.

Две детали:
  hand.stl  – кисть руки на подставке (печатать цветом кожи)
  heart.stl – зелёное сердечко со «вилкой»: две ножки с чашечками и штырями,
              которые садятся на кончики большого и указательного пальцев.

Размеры в мм. Запуск: python3 build.py  (нужны manifold3d, trimesh, numpy)
"""
import numpy as np
import trimesh
from manifold3d import Manifold, set_circular_segments

set_circular_segments(64)

# --- параметры крепления -------------------------------------------------
PEG_R = 1.5        # радиус штыря на сердечке (Ø3 мм)
HOLE_R = 1.75      # радиус отверстия в пальце (Ø3.5 мм, зазор 0.25 на сторону)
PEG_LEN = 6.0      # длина штыря
HOLE_DEPTH = 7.0   # глубина отверстия
CUP_GAP = 0.3      # зазор между чашечкой и кончиком пальца
FLAT_BACK_Y = 1.4  # срез задней стороны сердечка (смещение от оси, плоская спина для печати)


def sph(p, r):
    return Manifold.sphere(r).translate(p)


def capsule(*pts):
    """Цепочка шаров (x, y, z, r), соседние пары объединены оболочкой."""
    out = None
    for a, b in zip(pts, pts[1:]):
        seg = Manifold.batch_hull([sph(a[:3], a[3]), sph(b[:3], b[3])])
        out = seg if out is None else out + seg
    return out


def ellipse_cyl(cx, cy, z0, h, rx, ry):
    return Manifold.cylinder(h, 1.0).scale([rx, ry, 1]).translate([cx, cy, z0])


# --- кисть -----------------------------------------------------------------
# Ось Z вверх, зритель смотрит со стороны -Y.
AXIS_Y = -3.0
INDEX_TIP = (-14.0, AXIS_Y, 80.0, 6.5)
THUMB_TIP = (2.0, AXIS_Y, 80.0, 7.0)

base = Manifold.batch_hull([
    ellipse_cyl(0, -2, 0, 2.5, 34, 26),
    ellipse_cyl(0, -2, 2.5, 2.5, 32, 24),
])
wrist = Manifold.batch_hull([
    ellipse_cyl(4, 0, 3, 1, 16, 12),
    ellipse_cyl(3, 0, 20, 1, 17, 13),
])
fist = Manifold.batch_hull(
    [sph((x, y, z), 11) for x in (-11, 15) for y in (-3, 5) for z in (28, 44)]
    + [ellipse_cyl(3, 0, 20, 1, 17, 13)]
)

curled = []
for x, top in ((-4, 53), (7, 50), (17.5, 45)):  # средний, безымянный, мизинец
    curled.append(capsule((x, 0, top + 1, 6.3), (x, -10, top, 6.0),
                          (x, -14.5, top - 13, 5.8), (x, -13, top - 22, 5.4)))

index = capsule((-6, 1, 48, 7.0), (-11, -1, 65, 6.8), INDEX_TIP)
thumb = capsule((-23, -2, 30, 8.5), (-17, -10, 50, 7.8), (-8, -8, 66, 7.4), THUMB_TIP)

hand = base + wrist + fist + index + thumb
for c in curled:
    hand += c


def tip_top(tip):
    return tip[2] + tip[3]


def hole_for(tip):
    x, y, _, _ = tip
    top = tip_top(tip)
    return Manifold.cylinder(HOLE_DEPTH + 2, HOLE_R).translate([x, y, top - HOLE_DEPTH])


hand = hand - hole_for(INDEX_TIP) - hole_for(THUMB_TIP)

# --- сердечко ------------------------------------------------------------
HX = (INDEX_TIP[0] + THUMB_TIP[0]) / 2
H_BOTTOM = 91.0
LOBE_Z, LOBE_DX, LOBE_R = 108.0, 9.0, 11.0
DEPTH_SCALE = 0.75


def heart_shape():
    tip = sph((0, 0, H_BOTTOM + 4), 4.5)
    l = Manifold.batch_hull([sph((-LOBE_DX, 0, LOBE_Z), LOBE_R), tip])
    r = Manifold.batch_hull([sph((LOBE_DX, 0, LOBE_Z), LOBE_R), tip])
    return (l + r).scale([1, DEPTH_SCALE, 1]).translate([HX, AXIS_Y, 0])


def leg_to(tip):
    x, y, z, r = tip
    top = tip_top(tip)
    leg = Manifold.batch_hull([
        sph((HX, y, H_BOTTOM + 4), 3.6),
        Manifold.cylinder(1.0, 3.4).translate([x, y, top + 1.5]),
    ])
    cup = Manifold.cylinder(4.0, 5.0).translate([x, y, top - 1.8])
    peg = Manifold.cylinder(PEG_LEN + 0.5, PEG_R).translate([x, y, top - PEG_LEN])
    finger = sph((x, y, z), r + CUP_GAP)
    return (leg + cup - finger) + peg


heart = heart_shape() + leg_to(INDEX_TIP) + leg_to(THUMB_TIP)
# плоская спина: печатается лёжа лицом вверх без поддержек
heart = heart ^ Manifold.cube([200, 50, 200]).translate([-100, AXIS_Y + FLAT_BACK_Y - 50, 0])


def to_trimesh(m):
    mesh = m.to_mesh()
    return trimesh.Trimesh(mesh.vert_properties[:, :3], mesh.tri_verts, process=True)


if __name__ == "__main__":
    import os
    here = os.path.dirname(os.path.abspath(__file__))
    th, tr = to_trimesh(hand), to_trimesh(heart)
    th.export(os.path.join(here, "hand.stl"))
    # сердечко экспортируем уже уложенным на плоскую спину (лицом вверх)
    tr_print = tr.copy()
    tr_print.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [1, 0, 0]))
    tr_print.apply_translation(-tr_print.bounds[0])
    tr_print.export(os.path.join(here, "heart.stl"))

    # сборка с цветами для просмотра / мультицветной печати
    th.visual.face_colors = [240, 190, 150, 255]
    tr.visual.face_colors = [60, 170, 70, 255]
    scene = trimesh.Scene({"hand": th, "heart": tr})
    scene.export(os.path.join(here, "assembly.3mf"))
    for name, m in (("hand", th), ("heart", tr)):
        print(name, "watertight:", m.is_watertight, "size mm:", np.round(m.extents, 1),
              "volume cm3:", round(m.volume / 1000, 1))

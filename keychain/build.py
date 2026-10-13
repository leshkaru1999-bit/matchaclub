import numpy as np, trimesh, sys
from manifold3d import Manifold, set_circular_segments
set_circular_segments(64)
OUT = sys.argv[1]

def S(p, r, sc=(1,1,1)):
    return Manifold.sphere(r).scale(sc).translate(p)

def cap(a, b, r1, r2=None):
    return Manifold.batch_hull([S(a, r1), S(b, r2 or r1)])

def chain(pts, rs):
    m = None
    for i in range(len(pts)-1):
        c = cap(pts[i], pts[i+1], rs[i], rs[i+1])
        m = c if m is None else m + c
    return m

# --- hand (cartoon glove), units mm; x right, z up, -y = front ---
palm = S((1, 0, 0), 1, (10.5, 8.0, 11.5))
# curled middle/ring/pinky: each finger = knuckle -> mid -> tip curled into palm
fingers = None
for i, z in enumerate([6.0, -1.0, -8.0]):
    w = 4.2 - 0.25*i
    f = chain([(-3, -1, z+1), (-12, -2, z+1.5), (-13, -7, z-1.5), (-6, -8.5, z-2)],
              [w, w, w*0.95, w*0.9])
    fingers = f if fingers is None else fingers + f
# index finger: rises from top of fist, bends toward the thumb
index = chain([(-5, 0, 6), (-6, 0, 15), (-1, -0.5, 21.5), (3.5, -1, 23.5)],
              [4.6, 4.3, 4.0, 3.6])
# thumb: from right side, up and crossing in front of index tip
thumb = chain([(7, 1, -3), (10, 0, 8), (8, -2.5, 17), (3, -5, 23)],
              [5.6, 5.0, 4.4, 4.0])
# wrist / cuff stub
wrist = Manifold.cylinder(6, 7.5, 8.5).translate((1, 0, -16))
cuff  = Manifold.cylinder(3.5, 9.5, 9.5).translate((1, 0, -19))
hand = palm + fingers + index + thumb + wrist + cuff
# eyelet for the chain / jump ring
eyelet = (Manifold.cylinder(3, 4.2, 4.2, center=True) - Manifold.cylinder(4, 1.6, 1.6, center=True))
eyelet = eyelet.rotate((90, 0, 0)).translate((1, 0, -21.5))
hand = hand + eyelet

# --- heart ---
def heart(size=15.0, thick=7.5):
    r = size*0.29
    lobeL = S((-r*0.95, 0, 0), r)
    lobeR = S(( r*0.95, 0, 0), r)
    tip = S((0, 0, -size*0.78), 0.8)
    h = Manifold.batch_hull([lobeL, tip]) + Manifold.batch_hull([lobeR, tip])
    return h.scale((1, thick/(2*r), 1))
hc = (3.5, -2.5, 35.0)
h = heart().rotate((0, -15, 0)).translate(hc)
# peg on heart + matching hole in hand (for two-colour print, glue together)
peg_axis_bottom = (2.8, -2.5, 22.0)
peg  = Manifold.cylinder(7, 1.0, 1.0).rotate((0, -12, 0)).translate(peg_axis_bottom)
hole = Manifold.cylinder(7.5, 1.15, 1.15).rotate((0, -12, 0)).translate((peg_axis_bottom[0]+0.1, peg_axis_bottom[1], peg_axis_bottom[2]-0.5))

heart_part = h + peg
hand_part  = hand - hole - h   # pocket so heart sits snugly
full = hand + h

def to_tm(m):
    mesh = m.to_mesh()
    return trimesh.Trimesh(vertices=mesh.vert_properties[:, :3], faces=mesh.tri_verts)

parts = {"hand": to_tm(hand_part), "heart": to_tm(heart_part), "full": to_tm(full)}
for k, t in parts.items():
    t.export(f"{OUT}/{'keychain_full' if k=='full' else k}.stl")
    print(k, "watertight", t.is_watertight, "bbox", np.round(t.extents, 1), "vol", round(t.volume/1000, 2), "cm3")
# multicolour 3MF (two bodies, already aligned)
scene = trimesh.Scene()
th = to_tm(hand - h); th.visual.face_colors = [245,245,245,255]
tr = to_tm(h); tr.visual.face_colors = [220,30,30,255]
scene.add_geometry(th, node_name="hand_white"); scene.add_geometry(tr, node_name="heart_red")
scene.export(f"{OUT}/keychain_multicolor.3mf")




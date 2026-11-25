#!/usr/bin/env python3
"""
patron_vers_svg.py — Convertit un patron de couture scanné (PDF ou image)
en SVG à calques : un calque par taille, en traits continus.

Principe
--------
1. Chaque page est rendue en image noir et blanc à 300 dpi.
2. Chaque petite tache noire allongée est un « tiret » (ou un « point »).
3. Les tirets alignés et proches sont chaînés pour former des lignes.
4. Chaque ligne est attribuée à une taille selon la longueur de ses tirets
   et de ses espaces (voir MOTIFS ci-dessous).
5. Les coupures (croisements, angles, pointes de pinces) sont refermées.
6. Tout le reste (traits pleins, textes, flèches, crans) va dans un
   calque « Commun ».

Installation
------------
    pip install pymupdf opencv-python numpy scipy

Utilisation
-----------
    python patron_vers_svg.py patron.pdf
    python patron_vers_svg.py patron.pdf --pages 1 --exclure 1:0.912,0.02,1,0.66
    python patron_vers_svg.py patron.pdf --separer        # + un SVG par taille
    python patron_vers_svg.py scan.png --dpi 300          # une image marche aussi

--exclure PAGE:x0,y0,x1,y1 : zone (en fraction de la page, 0 à 1) dont les
pointillés vont dans « Commun » — pratique pour la légende ou un cartouche.
Peut être répété.

Adapter à un autre patron
-------------------------
Les longueurs de tirets ci-dessous ont été mesurées sur la légende d'un patron
La Maison Victor (tailles 34 à 42), en pixels à 300 dpi. Pour un autre
patron, mesurez les tirets de la légende (1 mm = 11,8 px à 300 dpi) et
modifiez la fonction classer_chaine() et tentative() si besoin.

    34 : points de 9, espaces de 8
    36 : tirets de 51, espaces de 8
    38 : tiret de 75 + petit tiret de 19, espaces de 18
    40 : tiret de 36 + point de 11 (espaces 7 et 35)
    42 : tirets de 51, espaces de 25
"""
import argparse
import math
import os
import sys

import cv2
import numpy as np
from scipy.spatial import cKDTree

sys.setrecursionlimit(100000)

# ----------------------------------------------------------------- réglages
DPI = 300
SEUIL_NOIR = 140          # niveau de gris sous lequel un pixel est « noir »
EPAISSEUR_MAX = 11        # épaisseur max d'un tiret (px)
LONGUEUR_MAX = 110        # longueur max d'un tiret isolé (px)
POINT_MAX = 15            # en dessous de cette longueur, c'est un « point »
TAILLES = [34, 36, 38, 40, 42]
COULEURS = {34: '#d62728', 36: '#2ca02c', 38: '#1f5fd6', 40: '#ff8c00', 42: '#b000b5'}
EPAISSEUR_TRAIT = 6       # épaisseur des traits dans le SVG (px à 300 dpi ≈ 0,5 mm)


# ------------------------------------------------------------ chargement
def charger_pages(chemin, dpi, pages=None):
    """Renvoie une liste de (numéro, image en niveaux de gris)."""
    ext = os.path.splitext(chemin)[1].lower()
    if ext == '.pdf':
        import pymupdf
        doc = pymupdf.open(chemin)
        nums = pages or list(range(1, len(doc) + 1))
        for n in nums:
            pix = doc[n - 1].get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
            img = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.width)
            yield n, img.copy()
    else:
        img = cv2.imread(chemin, cv2.IMREAD_GRAYSCALE)
        if img is None:
            sys.exit(f"Impossible de lire {chemin}")
        yield 1, img


# ------------------------------------------------- 1. détection des tirets
def detecter_tirets(b):
    n, lab, st, _ = cv2.connectedComponentsWithStats(b, connectivity=8)
    comps = {}
    for i in range(1, n):
        x, y, w, h, a = st[i]
        if max(w, h) > LONGUEUR_MAX or a < 12:
            continue
        ys, xs = np.nonzero(lab[y:y + h, x:x + w] == i)
        P = np.stack([xs + x, ys + y], 1).astype(float)
        m = P.mean(0)
        C = np.cov((P - m).T) if len(P) > 2 else np.eye(2)
        _, vec = np.linalg.eigh(C)
        d = vec[:, 1]
        pr = (P - m) @ d
        pp = (P - m) @ vec[:, 0]
        L = pr.max() - pr.min() + 1
        T = pp.max() - pp.min() + 1
        if T > EPAISSEUR_MAX or a / (L * T) < 0.55:
            continue                      # pas assez « tiret » (lettre, croisement…)
        point = L < POINT_MAX
        p0, p1 = (m, m) if point else (m + d * pr.min(), m + d * pr.max())
        comps[i] = dict(m=m, d=d, L=L, dot=point, p=[p0, p1])
    return comps, lab, st


# ------------------------------------------------ 2. chaînage des tirets
def chainer(comps):
    ids = list(comps)
    E, own = [], []
    for i in ids:
        for s in (0, 1):
            E.append(comps[i]['p'][s]); own.append((i, s))
    E = np.array(E)
    paires = cKDTree(E).query_pairs(46, output_type='ndarray')

    def sortie(c, s):
        return -c['d'] if s == 0 else c['d']

    cand = []
    for a_, b_ in paires:
        (i, si), (j, sj) = own[a_], own[b_]
        if i == j:
            continue
        ci, cj = comps[i], comps[j]
        v = E[b_] - E[a_]; g = np.linalg.norm(v)
        if ci['dot'] and cj['dot']:
            lim = 27
        elif ci['dot'] or cj['dot']:
            lim = 46
        else:
            lim = 33
        if g > lim or (ci['dot'] and cj['dot'] and si == sj == 1):
            continue
        cout, ok = g, True
        for c, s, vv in ((ci, si, v), (cj, sj, -v)):
            if c['dot']:
                continue
            od = sortie(c, s)
            le_long = vv @ od
            lat = abs(vv @ np.array([-od[1], od[0]]))
            if le_long < -3 or lat > max(4, 0.36 * max(le_long, 0)):
                ok = False; break
            cout += 3 * lat
        if not ok:
            continue
        if not ci['dot'] and not cj['dot'] and \
                sortie(ci, si) @ (-sortie(cj, sj)) < math.cos(math.radians(35)):
            continue
        cand.append((cout, i, si, j, sj, v / (g + 1e-9)))
    cand.sort(key=lambda t: t[0])

    lien, dirs_point = {}, {}

    def libres(i):
        return [s for s in (0, 1) if (i, s) not in lien]

    for _, i, si, j, sj, u in cand:
        if comps[i]['dot']:
            fr = libres(i)
            if not fr: continue
            si = fr[0]
        if comps[j]['dot']:
            fr = libres(j)
            if not fr: continue
            sj = fr[0]
        if (i, si) in lien or (j, sj) in lien:
            continue
        ok = True
        for k, uu in ((i, u), (j, -u)):        # un point doit rester « dans l'axe »
            if comps[k]['dot']:
                for w in dirs_point.get(k, []):
                    if w @ uu > -math.cos(math.radians(40)):
                        ok = False
        if not ok:
            continue
        lien[(i, si)] = (j, sj); lien[(j, sj)] = (i, si)
        if comps[i]['dot']: dirs_point.setdefault(i, []).append(u)
        if comps[j]['dot']: dirs_point.setdefault(j, []).append(-u)

    vus, chaines = set(), []
    for i in ids:
        if i in vus:
            continue
        cur, s, visite, cyc = i, 0, {i}, False
        while (cur, s) in lien:
            j, sj = lien[(cur, s)]
            if j in visite:
                cyc = True; break
            visite.add(j); cur, s = j, 1 - sj
        debut, entree = (i, 1) if cyc else (cur, s)
        seq, cur = [], debut
        while True:
            seq.append((cur, entree)); vus.add(cur)
            if (cur, 1 - entree) not in lien:
                break
            j, sj = lien[(cur, 1 - entree)]
            if j in vus:
                break
            cur, entree = j, sj
        chaines.append(dict(seq=seq, cyc=cyc))
    return chaines


# ------------------------------------------------ 3. classement par taille
def ecart(comps, a, b):
    (i, ei), (j, ej) = a, b
    return np.linalg.norm(comps[i]['p'][1 - ei] - comps[j]['p'][ej])


def classer_chaine(comps, seq):
    N = len(seq)
    if N < 3:
        return None
    Ls = np.array([comps[i]['L'] for i, _ in seq])
    pts = np.array([comps[i]['dot'] for i, _ in seq])
    tir = ~pts
    fd = pts.mean()
    fs = np.mean(tir & (Ls >= 14) & (Ls < 28))
    fm = np.mean(tir & (Ls >= 28) & (Ls < 44))
    fl = np.mean(tir & (Ls >= 44) & (Ls < 63))
    fx = np.mean(tir & (Ls >= 63))
    gaps = [ecart(comps, a, b) for a, b in zip(seq, seq[1:])
            if not comps[a[0]]['dot'] and not comps[b[0]]['dot']]
    score = {34: fd * 2 - fm - fl - fx,
             40: min(fd, fm) * 2.2,
             38: min(fs, fx) * 2.2,
             3642: fl}
    k = max(score, key=score.get)
    if score[k] < 0.3:
        return None
    if k == 3642:                      # 36 et 42 : même tiret, espace différent
        if not gaps:
            return None
        k = 36 if np.median(gaps) < 16 else 42
    return k


def tentative(comps, seq):
    """Taille(s) possible(s) pour un tronçon trop court (1 à 4 tirets)."""
    Ls = [comps[i]['L'] for i, _ in seq]
    dt = [comps[i]['dot'] for i, _ in seq]
    if all(dt):
        return [34] if len(seq) >= 2 else []
    nd = [L for L, d in zip(Ls, dt) if not d]
    if any(dt):
        return [40] if all(28 <= L < 46 for L in nd) else []
    if all(L >= 63 or 14 <= L < 28 for L in nd): return [38]
    if all(28 <= L < 44 for L in nd): return [40]
    if all(44 <= L < 63 for L in nd):
        if len(seq) >= 2:
            return [36] if ecart(comps, seq[0], seq[1]) < 16 else [42]
        return [36, 42]
    return []


# ---------------------------------------------- 4. raccord des coupures
def dir_extremite(pts, fin):
    P = pts if fin == 1 else pts[::-1]
    q = P[-1]; r = P[-2]
    for r in P[::-1][1:]:
        if np.linalg.norm(q - r) > 25:
            break
    d = q - r; n = np.linalg.norm(d)
    return q, (d / n if n > 0 else np.zeros(2))


def raccorder(lignes):
    while True:
        bouts = []
        for li, l in enumerate(lignes):
            if l['cyc']:
                continue
            for e in (0, 1):
                q, d = dir_extremite(l['pts'], e)
                bouts.append((li, e, q, d))
        best = None
        for a in range(len(bouts)):
            la, ea, qa, da = bouts[a]
            for b in range(a + 1, len(bouts)):
                lb, eb, qb, db = bouts[b]
                if lignes[la]['k'] != lignes[lb]['k']:
                    continue
                v = qb - qa; g = np.linalg.norm(v)
                if g > 220 or (la == lb and (g > 60 or len(lignes[la]['pts']) < 10)):
                    continue
                ok, cout, X = False, None, None
                al, bl = v @ da, -v @ db
                lat_a = abs(v @ np.array([-da[1], da[0]]))
                lat_b = abs(v @ np.array([-db[1], db[0]]))
                tol = max(6, 0.12 * g)
                if al > 0 and bl > 0 and lat_a < tol and lat_b < tol:
                    ok, cout = True, g + 2 * (lat_a + lat_b)          # dans l'alignement
                else:                                                # angle : on prolonge
                    M = np.array([da, -db]).T
                    if abs(np.linalg.det(M)) > 0.15 and g < 160:
                        ta, tb = np.linalg.solve(M, v)
                        if -8 < ta < 130 and -8 < tb < 130:
                            ok, cout, X = True, max(ta, 0) + max(tb, 0) + 30, qa + da * ta
                    if not ok and g < 30:
                        ok, cout = True, g * 2 + 40
                if ok and (best is None or cout < best[0]):
                    best = (cout, a, b, X)
        if best is None:
            return lignes
        _, a, b, X = best
        la, ea, _, _ = bouts[a]; lb, eb, _, _ = bouts[b]
        if la == lb:
            lignes[la]['cyc'] = True
            continue
        A, B = lignes[la]['pts'], lignes[lb]['pts']
        if ea == 0: A = A[::-1]
        if eb == 1: B = B[::-1]
        nouv = dict(k=lignes[la]['k'],
                    pts=np.vstack([A] + ([X[None]] if X is not None else []) + [B]),
                    ids=lignes[la]['ids'] + lignes[lb]['ids'], cyc=False,
                    tent=lignes[la]['tent'] and lignes[lb]['tent'])
        lignes = [l for i, l in enumerate(lignes) if i not in (la, lb)] + [nouv]


# ------------------------------------------------------------ 5. SVG
def contours_svg(m):
    cs, _ = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
    out = []
    for c in cs:
        c = cv2.approxPolyDP(c, 0.8, True).reshape(-1, 2)
        if len(c) >= 3:
            out.append('M' + ' '.join(f'{x},{y}' for x, y in c) + 'Z')
    return ''.join(out)


def rdp(P, eps=1.0):
    if len(P) < 3:
        return P
    a, b = P[0], P[-1]; d = b - a; n = np.linalg.norm(d); Q = P - a
    dist = np.linalg.norm(Q, axis=1) if n == 0 else np.abs(d[0] * Q[:, 1] - d[1] * Q[:, 0]) / n
    k = int(np.argmax(dist))
    if dist[k] > eps:
        return np.vstack([rdp(P[:k + 1], eps)[:-1], rdp(P[k:], eps)])
    return np.vstack([a, b])


def ecrire_svg(chemin, W, H, dpi, commun, nonclasse, lignes, tailles):
    mmw, mmh = W / dpi * 25.4, H / dpi * 25.4
    o = [f'<svg xmlns="http://www.w3.org/2000/svg" '
         f'xmlns:inkscape="http://www.inkscape.org/namespaces/inkscape" '
         f'width="{mmw:.2f}mm" height="{mmh:.2f}mm" viewBox="0 0 {W} {H}">',
         f'<g inkscape:groupmode="layer" inkscape:label="Commun (toutes tailles)" id="commun">'
         f'<path fill="#000" fill-rule="evenodd" d="{commun}"/></g>']
    if nonclasse is not None:
        o.append(f'<g inkscape:groupmode="layer" inkscape:label="Non classé (à vérifier)" '
                 f'id="nonclasse" style="display:none"><path fill="#888" d="{nonclasse}"/></g>')
    for k in tailles:
        o.append(f'<g inkscape:groupmode="layer" inkscape:label="Taille {k}" id="taille{k}" '
                 f'fill="none" stroke="{COULEURS.get(k, "#000")}" stroke-width="{EPAISSEUR_TRAIT}" '
                 f'stroke-linejoin="round" stroke-linecap="round">')
        for l in lignes:
            if l['k'] != k:
                continue
            P = l['pts']
            P = rdp(P[np.r_[True, np.linalg.norm(np.diff(P, axis=0), axis=1) > 0.5]])
            o.append('<path d="M' + ' L'.join(f'{x:.1f},{y:.1f}' for x, y in P)
                     + ('Z' if l['cyc'] else '') + '"/>')
        o.append('</g>')
    o.append('</svg>')
    with open(chemin, 'w', encoding='utf-8') as f:
        f.write('\n'.join(o))


# ------------------------------------------------------------ une page
def traiter_page(img, zones, dpi):
    H, W = img.shape

    def exclu(p):
        return any(x0 * W <= p[0] <= x1 * W and y0 * H <= p[1] <= y1 * H
                   for x0, y0, x1, y1 in zones)

    b = (img < SEUIL_NOIR).astype(np.uint8)
    comps, lab, st = detecter_tirets(b)
    chaines = chainer(comps)

    def points(seq):
        pts = []
        for i, e in seq:
            p = comps[i]['p']; pts += [p[e], p[1 - e]]
        return np.array(pts)

    lignes = []
    for c in chaines:
        seq = list(c['seq'])
        k = classer_chaine(comps, seq)
        if k is not None:
            if k == 34:   # une ligne de points ne finit pas par un tiret (cran)
                while seq and not comps[seq[0][0]]['dot']: seq.pop(0)
                while seq and not comps[seq[-1][0]]['dot']: seq.pop()
            if len(seq) < 3:
                continue
            pts = points(seq)
            if not exclu(pts.mean(0)):
                lignes.append(dict(k=k, pts=pts, ids=[i for i, _ in seq], cyc=c['cyc'], tent=False))
        elif len(seq) <= 4:
            pts = points(seq)
            if not exclu(pts.mean(0)):
                for kk in tentative(comps, seq):
                    lignes.append(dict(k=kk, pts=pts, ids=[i for i, _ in seq], cyc=False, tent=True))

    lignes = raccorder(lignes)
    lignes = [l for l in lignes if not l['tent']
              and np.linalg.norm(np.diff(l['pts'], axis=0), axis=1).sum() > 60]

    # calque commun = pixels noirs moins les tirets utilisés
    utilises = set(i for l in lignes for i in l['ids'])
    commun = b.copy()
    nonclasse = np.zeros_like(b)

    def deplacer(labs, stats, i, vers):
        x, y, w, h = stats[i][:4]
        sel = labs[y:y + h, x:x + w] == i
        commun[y:y + h, x:x + w][sel] = 0
        if vers is not None:
            vers[y:y + h, x:x + w][sel] = 1

    for i in utilises:
        deplacer(lab, st, i, None)
    for i in comps:
        if i not in utilises and not exclu(comps[i]['m']):
            deplacer(lab, st, i, nonclasse)
    # petits morceaux restés collés sur une ligne classée (croisements) -> non classé
    masque = np.zeros_like(b)
    for l in lignes:
        cv2.polylines(masque, [l['pts'].astype(np.int32)], l['cyc'], 1, 13)
    n2, lab2, st2, _ = cv2.connectedComponentsWithStats(commun, connectivity=8)
    for i in range(1, n2):
        x, y, w, h, a = st2[i]
        if max(w, h) > 130 or a > 1500:
            continue
        sel = lab2[y:y + h, x:x + w] == i
        if masque[y:y + h, x:x + w][sel].mean() > 0.6:
            deplacer(lab2, st2, i, nonclasse)
    return W, H, lignes, contours_svg(commun), contours_svg(nonclasse)


# ------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('entree', help='PDF ou image du patron')
    ap.add_argument('--pages', help='pages à traiter, ex. 1,2 (défaut : toutes)')
    ap.add_argument('--dpi', type=int, default=DPI, help='résolution de rendu (défaut 300)')
    ap.add_argument('--exclure', action='append', default=[],
                    help='PAGE:x0,y0,x1,y1 zone à ignorer (fractions 0-1), répétable')
    ap.add_argument('--separer', action='store_true', help='écrire aussi un SVG par taille')
    ap.add_argument('--sortie', default='.', help='dossier de sortie')
    args = ap.parse_args()

    if args.dpi != 300:
        print("Attention : les longueurs de tirets sont calibrées pour 300 dpi.")
    pages = [int(p) for p in args.pages.split(',')] if args.pages else None
    zones = {}
    for z in args.exclure:
        p, r = z.split(':')
        zones.setdefault(int(p), []).append(tuple(float(v) for v in r.split(',')))

    os.makedirs(args.sortie, exist_ok=True)
    base = os.path.splitext(os.path.basename(args.entree))[0]
    for num, img in charger_pages(args.entree, args.dpi, pages):
        print(f"Page {num} : analyse…", flush=True)
        W, H, lignes, commun, nonclasse = traiter_page(img, zones.get(num, []), args.dpi)
        nb = {k: sum(l['k'] == k for l in lignes) for k in TAILLES}
        print("   lignes par taille :", nb)
        f = os.path.join(args.sortie, f"{base}-page{num}.svg")
        ecrire_svg(f, W, H, args.dpi, commun, nonclasse, lignes, TAILLES)
        print("   ->", f)
        if args.separer:
            for k in TAILLES:
                fk = os.path.join(args.sortie, f"{base}-page{num}-taille{k}.svg")
                ecrire_svg(fk, W, H, args.dpi, commun, None, lignes, [k])


if __name__ == '__main__':
    main()

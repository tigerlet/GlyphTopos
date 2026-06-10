import numpy as np
from fontTools.pens.basePen import BasePen


class PrecisionPen(BasePen):
    """High-precision glyph contour pen, adaptively samples glyph paths into polygon contours."""

    def __init__(self, glyphSet, tolerance=0.1):
        super().__init__(glyphSet)
        self.contours = []
        self.current_path = []
        self.tolerance = tolerance

    def _flush_path(self):
        if self.current_path:
            points = np.array(self.current_path)
            area = self._signed_area(points)
            self.contours.append({
                "points": points,
                "type": "inner" if area < 0 else "outer",
            })
            self.current_path = []

    def _moveTo(self, pt):
        self._flush_path()
        self.current_path.append(pt)

    def _lineTo(self, pt):
        self.current_path.append(pt)

    def _closePath(self):
        self._flush_path()

    def _signed_area(self, points):
        x, y = points[:, 0], points[:, 1]
        return 0.5 * (x @ np.roll(y, 1) - y @ np.roll(x, 1))

    def _curveToOne(self, pt1, pt2, pt3):
        p0 = self.current_path[-1]
        points = self._adaptive_sample(p0, pt1, pt2, pt3)
        self.current_path.extend(points)

    def _adaptive_sample(self, p0, p1, p2, p3, depth=0):
        if depth > 8 or self._flatness(p0, p1, p2, p3) < self.tolerance:
            return [p3]
        mid = 0.5
        q0 = tuple(a * (1 - mid) + b * mid for a, b in zip(p0, p1))
        q1 = tuple(a * (1 - mid) + b * mid for a, b in zip(p1, p2))
        q2 = tuple(a * (1 - mid) + b * mid for a, b in zip(p2, p3))
        r0 = tuple(a * (1 - mid) + b * mid for a, b in zip(q0, q1))
        r1 = tuple(a * (1 - mid) + b * mid for a, b in zip(q1, q2))
        split = tuple(a * (1 - mid) + b * mid for a, b in zip(r0, r1))
        return self._adaptive_sample(p0, q0, r0, split, depth + 1) + self._adaptive_sample(split, r1, q2, p3, depth + 1)

    def _flatness(self, p0, p1, p2, p3):
        ux = 3 * p1[0] - 2 * p0[0] - p3[0]
        uy = 3 * p1[1] - 2 * p0[1] - p3[1]
        vx = 3 * p2[0] - 2 * p3[0] - p0[0]
        vy = 3 * p2[1] - 2 * p3[1] - p0[1]
        return max(ux * ux + uy * uy, vx * vx + vy * vy)

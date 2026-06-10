import numpy as np
from fontTools.ttLib import TTFont

from .pen import PrecisionPen


class GlyphAnalyzer:
    """Glyph analyzer, responsible for loading fonts, extracting contours, and computing geometric and topological information."""

    def __init__(self, font_path):
        self.font = TTFont(font_path)
        self.glyph_set = self.font.getGlyphSet()
        self.glyph_order = self.font.getGlyphOrder()
        self.cmap = {}
        for table in self.font["cmap"].tables:
            if table.isUnicode():
                self.cmap.update(table.cmap)

    def get_glyph_name(self, char_or_name):
        if len(char_or_name) == 1:
            cp = ord(char_or_name)
            if cp in self.cmap:
                return self.cmap[cp]
            raise ValueError(f"Character '{char_or_name}' (U+{cp:04X}) is not in the font")
        return char_or_name

    def _signed_area(self, points):
        x, y = points[:, 0], points[:, 1]
        return 0.5 * (x @ np.roll(y, 1) - y @ np.roll(x, 1))

    def _contains(self, parent, child):
        return all(self._point_inside(p, parent) for p in child)

    def _point_inside(self, pt, polygon):
        x, y = pt
        inside = False
        n = len(polygon)
        for i in range(n):
            p1, p2 = polygon[i], polygon[(i + 1) % n]
            if (p1[1] > y) != (p2[1] > y):
                t = (y - p1[1]) / (p2[1] - p1[1]) if (p2[1] - p1[1]) != 0 else 0
                xc = p1[0] + t * (p2[0] - p1[0])
                if x <= xc:
                    inside = not inside
        return inside

    def analyze(self, char_or_name):
        glyph_name = self.get_glyph_name(char_or_name)
        glyph = self.glyph_set[glyph_name]
        pen = PrecisionPen(self.glyph_set)
        glyph.draw(pen)
        contours = pen.contours

        if not contours:
            return None

        self._correct_types(contours)
        components = self._group_components(contours)

        outer_count = sum(1 for c in contours if c["type"] == "outer")
        inner_count = sum(1 for c in contours if c["type"] == "inner")
        bbox = self._bbox(contours)

        return {
            "glyph_name": char_or_name,
            "real_glyph_name": glyph_name,
            "contour_count": len(contours),
            "component_count": len(components),
            "outer_contours": outer_count,
            "inner_contours": inner_count,
            "bbox": bbox,
            "width": bbox[2] - bbox[0],
            "height": bbox[3] - bbox[1],
            "contours": contours,
            "components": components,
            "metrics": self._metrics(contours),
            "topology": self._topology(contours),
            "component_topology": self._component_topology(components),
        }

    def _correct_types(self, contours):
        if len(contours) <= 1:
            if contours:
                contours[0]["type"] = "outer"
            return
        parents = [-1] * len(contours)
        for j, child in enumerate(contours):
            best_parent = -1
            best_diff = float("inf")
            for i, parent in enumerate(contours):
                if i != j and self._contains(parent["points"], child["points"]):
                    pa = abs(self._signed_area(parent["points"]))
                    ca = abs(self._signed_area(child["points"]))
                    diff = pa - ca
                    if best_parent == -1 or (diff < best_diff and diff > 0):
                        best_parent = i
                        best_diff = diff
            parents[j] = best_parent
        depths = [0] * len(contours)
        for i in range(len(contours)):
            d, p = 0, parents[i]
            while p != -1:
                d += 1
                p = parents[p]
            depths[i] = d
        for i, c in enumerate(contours):
            c["type"] = "outer" if depths[i] % 2 == 0 else "inner"

    def _group_components(self, contours):
        components = []
        outers = [i for i, c in enumerate(contours) if c["type"] == "outer"]
        for oi in outers:
            comp = {"outer_index": oi, "inner_indices": [], "contours": [contours[oi]]}
            for ii, c in enumerate(contours):
                if c["type"] == "inner":
                    if self._contains(contours[oi]["points"], c["points"]):
                        has_parent = False
                        for oo in outers:
                            if oo != oi and self._contains(contours[oo]["points"], c["points"]):
                                oa = abs(self._signed_area(contours[oi]["points"]))
                                oa2 = abs(self._signed_area(contours[oo]["points"]))
                                if oa2 < oa:
                                    has_parent = True
                                    break
                        if not has_parent:
                            comp["inner_indices"].append(ii)
                            comp["contours"].append(c)
            components.append(comp)
        return components

    def _bbox(self, contours):
        all_pts = np.vstack([c["points"] for c in contours])
        return (
            float(all_pts[:, 0].min()),
            float(all_pts[:, 1].min()),
            float(all_pts[:, 0].max()),
            float(all_pts[:, 1].max()),
        )

    def _metrics(self, contours):
        metrics = []
        for c in contours:
            points = c["points"]
            area = abs(self._signed_area(points))
            perimeter = float(np.sum(np.linalg.norm(np.diff(points, axis=0), axis=1)))
            compactness = (4 * np.pi * area) / (perimeter ** 2) if perimeter else 0
            metrics.append({
                "area": float(area),
                "perimeter": perimeter,
                "compactness": float(compactness),
                "orientation": "CCW (counter-clockwise)" if self._signed_area(points) > 0 else "CW (clockwise)",
                "type": c["type"],
                "point_count": len(points),
            })
        return metrics

    def _topology(self, contours):
        hierarchy = []
        for i, c in enumerate(contours):
            if c["type"] == "inner":
                parent = -1
                best_area = float("inf")
                for j, p in enumerate(contours):
                    if j != i and p["type"] == "outer":
                        if self._contains(p["points"], c["points"]):
                            a = abs(self._signed_area(p["points"]))
                            if a < best_area:
                                best_area = a
                                parent = j
                hierarchy.append({"child": i, "parent": parent})
        return hierarchy

    def _component_topology(self, components):
        """Detect nesting relationships between components: component A contains component B iff B's outer contour lies inside A's outer contour."""
        relations = []
        n = len(components)
        for bi in range(n):
            b_comp = components[bi]
            b_outer = b_comp["contours"][0]["points"]
            b_area = abs(self._signed_area(b_outer))
            best_parent = -1
            best_area = float("inf")
            for ai in range(n):
                if ai == bi:
                    continue
                a_comp = components[ai]
                a_outer = a_comp["contours"][0]["points"]
                if self._contains(a_outer, b_outer):
                    a_area = abs(self._signed_area(a_outer))
                    if a_area < best_area:
                        best_area = a_area
                        best_parent = ai
            if best_parent != -1:
                relations.append({
                    "child": bi,
                    "parent": best_parent,
                    "child_area": b_area,
                    "parent_area": best_area,
                })
        return relations

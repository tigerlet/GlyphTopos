import tkinter as tk
from tkinter import ttk, filedialog, messagebox, scrolledtext
import numpy as np
from fontTools.ttLib import TTFont
from fontTools.pens.basePen import BasePen
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk
from matplotlib import rcParams
import platform

if platform.system() == "Windows":
    rcParams["font.sans-serif"] = ["SimHei"]
elif platform.system() == "Darwin":
    rcParams["font.sans-serif"] = ["Arial Unicode MS"]
else:
    rcParams["font.sans-serif"] = ["WenQuanYi Zen Hei"]
rcParams["axes.unicode_minus"] = False


class PrecisionPen(BasePen):
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


class GlyphAnalyzer:
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
        """Detect nesting between components: component A contains component B iff B's outer contour lies inside A's outer contour."""
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


class GlyphAnalyzerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Glyph Contour Analyzer")
        self.root.geometry("1280x820")
        self.root.minsize(900, 600)

        self.analyzer = None
        self.current_result = None
        self.current_font_path = "simkai.ttf"

        self._build_style()
        self._build_layout()
        self._try_load_default_font()

    def _build_style(self):
        style = ttk.Style()
        try:
            style.theme_use("clam")
        except Exception:
            pass
        style.configure("Title.TLabel", font=("Microsoft YaHei", 12, "bold"))
        style.configure("Section.TLabelframe.Label", font=("Microsoft YaHei", 10, "bold"))
        style.configure("Key.TLabel", font=("Microsoft YaHei", 9), foreground="#555")
        style.configure("Value.TLabel", font=("Consolas", 10), foreground="#111")
        style.configure("Header.TLabel", font=("Microsoft YaHei", 9, "bold"), background="#eaeaea", padding=4)
        style.configure("Cell.TLabel", font=("Consolas", 9), padding=3)
        style.configure("Accent.TButton", font=("Microsoft YaHei", 10, "bold"))

    def _build_layout(self):
        main = ttk.Frame(self.root, padding=8)
        main.pack(fill="both", expand=True)

        self._build_toolbar(main)

        body = ttk.PanedWindow(main, orient="horizontal")
        body.pack(fill="both", expand=True, pady=(8, 0))

        left_frame = ttk.Frame(body, padding=4)
        right_frame = ttk.Frame(body, padding=4)

        body.add(left_frame, weight=2)
        body.add(right_frame, weight=1)

        self._build_outline_panel(left_frame)
        self._build_data_panel(right_frame)

        self._build_statusbar(main)

    def _build_toolbar(self, parent):
        bar = ttk.Frame(parent)
        bar.pack(fill="x")

        ttk.Label(bar, text="Font file:", style="Key.TLabel").pack(side="left", padx=(0, 4))
        self.font_var = tk.StringVar(value=self.current_font_path)
        ttk.Entry(bar, textvariable=self.font_var, width=30).pack(side="left", padx=(0, 4))
        ttk.Button(bar, text="Browse…", command=self.pick_font).pack(side="left", padx=(0, 8))

        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=6)

        ttk.Label(bar, text="Char / glyph name:", style="Key.TLabel").pack(side="left", padx=(0, 4))
        self.char_var = tk.StringVar(value="A")
        entry = ttk.Entry(bar, textvariable=self.char_var, width=16)
        entry.pack(side="left", padx=(0, 4))
        entry.bind("<Return>", lambda e: self.analyze())

        ttk.Button(bar, text="Analyze", style="Accent.TButton", command=self.analyze).pack(side="left", padx=(0, 4))
        ttk.Button(bar, text="Previous", command=self.prev_glyph).pack(side="left", padx=2)
        ttk.Button(bar, text="Next", command=self.next_glyph).pack(side="left", padx=2)

        ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=6)

        ttk.Label(bar, text="Show:", style="Key.TLabel").pack(side="left", padx=(0, 4))
        self.show_outer = tk.BooleanVar(value=True)
        self.show_inner = tk.BooleanVar(value=True)
        self.show_points = tk.BooleanVar(value=False)
        self.show_fill = tk.BooleanVar(value=True)
        ttk.Checkbutton(bar, text="Outer", variable=self.show_outer, command=self.refresh_plot).pack(side="left")
        ttk.Checkbutton(bar, text="Inner", variable=self.show_inner, command=self.refresh_plot).pack(side="left")
        ttk.Checkbutton(bar, text="Vertices", variable=self.show_points, command=self.refresh_plot).pack(side="left")
        ttk.Checkbutton(bar, text="Fill", variable=self.show_fill, command=self.refresh_plot).pack(side="left")

    def _build_outline_panel(self, parent):
        frame = ttk.Labelframe(parent, text=" Glyph Outline ", style="Section.TLabelframe")
        frame.pack(fill="both", expand=True)

        self.figure = Figure(figsize=(6, 5), dpi=100, facecolor="#ffffff")
        self.ax = self.figure.add_subplot(111)
        self.ax.set_aspect("equal")
        self.ax.axis("off")
        self.figure.tight_layout(pad=2)

        self.canvas = FigureCanvasTkAgg(self.figure, master=frame)
        self.canvas.get_tk_widget().pack(fill="both", expand=True)

        toolbar = NavigationToolbar2Tk(self.canvas, frame)
        toolbar.update()
        toolbar.pack(side="bottom", fill="x")

    def _build_data_panel(self, parent):
        top = ttk.Frame(parent)
        top.pack(fill="both", expand=True)

        canvas = tk.Canvas(top, highlightthickness=0)
        vsb = ttk.Scrollbar(top, orient="vertical", command=canvas.yview)
        inner = ttk.Frame(canvas)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        def on_mousewheel(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        canvas.bind_all("<MouseWheel>", on_mousewheel)

        col = 0
        inner.columnconfigure(col, weight=1)

        self._build_basic_info(inner)
        self._build_geometry_table(inner)
        self._build_components_info(inner)
        self._build_topology_info(inner)
        self._build_component_topology_info(inner)

    def _build_basic_info(self, parent):
        f = ttk.Labelframe(parent, text=" Basic Info ", style="Section.TLabelframe", padding=8)
        f.pack(fill="x", pady=(0, 8))
        for i in range(4):
            f.columnconfigure(i, weight=1)

        self.info_labels = {}
        items = [
            ("Glyph", "glyph"),
            ("Glyph name", "name"),
            ("Contours", "contours"),
            ("Components", "components"),
            ("Outer", "outer"),
            ("Inner", "inner"),
            ("Width", "width"),
            ("Height", "height"),
        ]
        for idx, (label, key) in enumerate(items):
            r, c = divmod(idx, 4)
            cell = ttk.Frame(f)
            cell.grid(row=r, column=c, sticky="we", padx=4, pady=3)
            ttk.Label(cell, text=f"{label}: ", style="Key.TLabel").pack(side="left")
            val = ttk.Label(cell, text="—", style="Value.TLabel")
            val.pack(side="left")
            self.info_labels[key] = val

    def _build_geometry_table(self, parent):
        f = ttk.Labelframe(parent, text=" Contour Geometry ", style="Section.TLabelframe", padding=6)
        f.pack(fill="x", pady=(0, 8))

        columns = ("idx", "ctype", "orient", "area", "perim", "compact", "points")
        headers = ("#", "Type", "Orientation", "Area", "Perimeter", "Compactness", "Points")
        col_widths = (40, 45, 120, 80, 80, 100, 55)

        tv = ttk.Treeview(
            f, columns=columns, show="headings",
            height=8, selectmode="none",
        )
        for col, hdr, w in zip(columns, headers, col_widths):
            tv.heading(col, text=hdr)
            anchor = "center" if col in ("idx", "ctype") else "e"
            tv.column(col, width=w, anchor=anchor, stretch=False)

        tv.tag_configure("odd", background="#f5f7fa")
        tv.tag_configure("even", background="#ffffff")

        vsb = ttk.Scrollbar(f, orient="vertical", command=tv.yview)
        tv.configure(yscrollcommand=vsb.set)
        tv.pack(side="left", fill="x", expand=True)

        self.metrics_tree = tv

    def _build_components_info(self, parent):
        f = ttk.Labelframe(parent, text=" Component Structure ", style="Section.TLabelframe", padding=6)
        f.pack(fill="x", pady=(0, 8))
        self.components_text = scrolledtext.ScrolledText(
            f, height=12, font=("Consolas", 10), relief="solid", bd=1, wrap="word"
        )
        self.components_text.pack(fill="both", expand=True)

    def _build_topology_info(self, parent):
        f = ttk.Labelframe(parent, text=" Contour Topology ", style="Section.TLabelframe", padding=6)
        f.pack(fill="x", pady=(0, 8))
        self.topology_text = scrolledtext.ScrolledText(
            f, height=4, font=("Consolas", 10), relief="solid", bd=1, wrap="word"
        )
        self.topology_text.pack(fill="both", expand=True)

    def _build_component_topology_info(self, parent):
        f = ttk.Labelframe(parent, text=" Component Topology ", style="Section.TLabelframe", padding=6)
        f.pack(fill="x", pady=(0, 8))
        self.component_topology_text = scrolledtext.ScrolledText(
            f, height=5, font=("Consolas", 10), relief="solid", bd=1, wrap="word"
        )
        self.component_topology_text.pack(fill="both", expand=True)

    def _build_statusbar(self, parent):
        self.status = tk.StringVar(value="Ready")
        bar = ttk.Frame(parent)
        bar.pack(fill="x", pady=(6, 0))
        ttk.Label(bar, textvariable=self.status, style="Key.TLabel").pack(side="left")

    def _try_load_default_font(self):
        try:
            self.analyzer = GlyphAnalyzer(self.current_font_path)
            self.status.set(f"Font loaded: {self.current_font_path} ({len(self.analyzer.glyph_order)} glyphs)")
            self.analyze()
        except Exception as e:
            self.status.set(f"Failed to load default font: {e}")

    def pick_font(self):
        path = filedialog.askopenfilename(
            title="Select a font file",
            filetypes=[("Font files", "*.ttf *.otf *.ttc"), ("All files", "*.*")],
        )
        if path:
            self.current_font_path = path
            self.font_var.set(path)
            try:
                self.analyzer = GlyphAnalyzer(path)
                self.status.set(f"Font loaded: {path} ({len(self.analyzer.glyph_order)} glyphs)")
                self.analyze()
            except Exception as e:
                messagebox.showerror("Load failed", f"Cannot load font file:\n{e}")

    def analyze(self):
        if not self.analyzer:
            messagebox.showwarning("Notice", "Please select and load a font file first")
            return
        text = self.char_var.get().strip()
        if not text:
            return
        try:
            result = self.analyzer.analyze(text)
            if result is None:
                messagebox.showinfo("No data", f"Character '{text}' has no contour data")
                return
            self.current_result = result
            self._populate_data(result)
            self.draw_outline(result)
            self.status.set(f"Analyzed: {text}")
        except Exception as e:
            messagebox.showerror("Analysis failed", str(e))

    def _step_glyph(self, step):
        if not self.analyzer:
            return
        text = self.char_var.get().strip()
        try:
            glyph_name = self.analyzer.get_glyph_name(text)
        except Exception:
            glyph_name = self.analyzer.glyph_order[0]
        try:
            idx = self.analyzer.glyph_order.index(glyph_name)
        except ValueError:
            idx = 0
        idx = (idx + step) % len(self.analyzer.glyph_order)
        new_name = self.analyzer.glyph_order[idx]
        self.char_var.set(new_name)
        self.analyze()

    def next_glyph(self):
        self._step_glyph(1)

    def prev_glyph(self):
        self._step_glyph(-1)

    def refresh_plot(self):
        if self.current_result is not None:
            self.draw_outline(self.current_result)

    def draw_outline(self, result):
        self.ax.clear()
        contours = result["contours"]

        outer_color = "#2d6cdf"
        inner_color = "#e94b3c"

        if self.show_fill.get():
            all_x = []
            all_y = []
            for c in contours:
                pts = c["points"]
                all_x.extend(pts[:, 0].tolist())
                all_y.extend(pts[:, 1].tolist())
            try:
                paths = []
                from matplotlib.path import Path
                import matplotlib.patches as patches
                verts = []
                codes = []
                for c in contours:
                    pts = c["points"]
                    if len(pts) < 2:
                        continue
                    verts.append((pts[0][0], pts[0][1]))
                    codes.append(Path.MOVETO)
                    for p in pts[1:]:
                        verts.append((p[0], p[1]))
                        codes.append(Path.LINETO)
                    verts.append((0, 0))
                    codes.append(Path.CLOSEPOLY)
                if verts:
                    path = Path(verts, codes)
                    patch = patches.PathPatch(path, facecolor="#4ECDC4", edgecolor="none",
                                              lw=0, alpha=0.35)
                    self.ax.add_patch(patch)
            except Exception:
                pass

        for idx, c in enumerate(contours):
            pts = c["points"]
            if len(pts) < 2:
                continue
            if not np.array_equal(pts[0], pts[-1]):
                pts = np.vstack([pts, pts[0:1]])
            is_outer = c["type"] == "outer"
            if is_outer and not self.show_outer.get():
                continue
            if not is_outer and not self.show_inner.get():
                continue
            color = outer_color if is_outer else inner_color
            ls = "-" if is_outer else "--"
            label = f"Outer {idx}" if is_outer else f"Inner {idx}"
            self.ax.plot(pts[:, 0], pts[:, 1], color=color, linestyle=ls,
                         linewidth=1.5, label=label)
            if self.show_points.get():
                self.ax.scatter(pts[:, 0], pts[:, 1], s=6, color=color, zorder=5)

        bbox = result["bbox"]
        w, h = result["width"], result["height"]
        pad = max(w, h) * 0.12 if (w or h) else 10
        self.ax.set_xlim(bbox[0] - pad, bbox[2] + pad)
        self.ax.set_ylim(bbox[1] - pad, bbox[3] + pad)
        self.ax.set_aspect("equal")
        self.ax.set_title(f"Glyph: {result['glyph_name']}  ({result['real_glyph_name']})",
                          fontsize=11, fontweight="bold")
        self.ax.axis("off")
        if len(contours) <= 12:
            self.ax.legend(loc="upper left", fontsize=8, framealpha=0.9,
                            bbox_to_anchor=(1.02, 1.0), borderaxespad=0.)
        self.figure.tight_layout(rect=[0, 0, 0.80, 1], pad=2)
        self.canvas.draw()

    def _populate_data(self, result):
        self.info_labels["glyph"].configure(text=result["glyph_name"])
        self.info_labels["name"].configure(text=result["real_glyph_name"])
        self.info_labels["contours"].configure(text=str(result["contour_count"]))
        self.info_labels["components"].configure(text=str(result["component_count"]))
        self.info_labels["outer"].configure(text=str(result["outer_contours"]))
        self.info_labels["inner"].configure(text=str(result["inner_contours"]))
        self.info_labels["width"].configure(text=f"{result['width']:.1f}")
        self.info_labels["height"].configure(text=f"{result['height']:.1f}")

        for item in self.metrics_tree.get_children():
            self.metrics_tree.delete(item)
        for i, m in enumerate(result["metrics"]):
            ctype = "Outer" if m["type"] == "outer" else "Inner"
            values = (
                str(i + 1), ctype, m["orientation"],
                f"{m['area']:.1f}", f"{m['perimeter']:.1f}",
                f"{m['compactness']:.4f}", str(m["point_count"]),
            )
            tag = "even" if i % 2 == 0 else "odd"
            self.metrics_tree.insert("", "end", values=values, tags=(tag,))

        self.components_text.delete("1.0", "end")
        for idx, comp in enumerate(result["components"]):
            oi = comp["outer_index"] + 1
            inners = ", ".join([str(x + 1) for x in comp["inner_indices"]]) or "none"
            ctype = "Complex polygon with holes" if comp["inner_indices"] else "Simple polygon"
            self.components_text.insert("end",
                f"Component {idx + 1}:\n  Outer contour: contour {oi}\n  Inner contours: {inners}\n  Type: {ctype}\n\n")

        self.topology_text.delete("1.0", "end")
        if result["topology"]:
            for rel in result["topology"]:
                self.topology_text.insert("end",
                    f"Contour {rel['child'] + 1} (Inner)  ⊂  Contour {rel['parent'] + 1} (Outer)\n")
        else:
            self.topology_text.insert("end", "No nesting relationships\n")

        self.component_topology_text.delete("1.0", "end")
        comp_topo = result.get("component_topology", [])
        if comp_topo:
            for rel in comp_topo:
                self.component_topology_text.insert("end",
                    f"Component {rel['child'] + 1}  ⊂  Component {rel['parent'] + 1}"
                    f"   (area ratio {rel['child_area']:.0f} / {rel['parent_area']:.0f})\n")
        else:
            self.component_topology_text.insert("end", "All components are independent; no nesting\n")


def main():
    root = tk.Tk()
    app = GlyphAnalyzerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

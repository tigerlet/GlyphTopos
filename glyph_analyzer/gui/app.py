import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import numpy as np

from ..analyzer import GlyphAnalyzer
from .styles import build_style
from .toolbar import build_toolbar
from .panels import build_outline_panel, build_data_panel


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
        build_style()

    def _build_layout(self):
        main = ttk.Frame(self.root, padding=8)
        main.pack(fill="both", expand=True)

        self.font_var = tk.StringVar(value=self.current_font_path)
        self.char_var = tk.StringVar(value="A")
        self.show_outer = tk.BooleanVar(value=True)
        self.show_inner = tk.BooleanVar(value=True)
        self.show_points = tk.BooleanVar(value=False)
        self.show_fill = tk.BooleanVar(value=True)

        self._build_toolbar(main)

        body = ttk.PanedWindow(main, orient="horizontal")
        body.pack(fill="both", expand=True, pady=(8, 0))

        left_frame = ttk.Frame(body, padding=4)
        right_frame = ttk.Frame(body, padding=4)

        body.add(left_frame, weight=2)
        body.add(right_frame, weight=1)

        self.figure, self.ax, self.canvas = build_outline_panel(left_frame)
        (self.info_labels, self.metrics_tree, self.components_text,
         self.topology_text, self.component_topology_text) = build_data_panel(right_frame)

        self._build_statusbar(main)

    def _build_toolbar(self, parent):
        build_toolbar(
            parent,
            self.font_var, self.char_var,
            self.show_outer, self.show_inner, self.show_points, self.show_fill,
            on_pick_font=self.pick_font,
            on_analyze=self.analyze,
            on_prev=self.prev_glyph,
            on_next=self.next_glyph,
            on_refresh=self.refresh_plot,
        )

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

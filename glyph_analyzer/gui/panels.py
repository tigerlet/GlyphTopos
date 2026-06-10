import tkinter as tk
from tkinter import ttk, scrolledtext
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg, NavigationToolbar2Tk


def build_outline_panel(parent):
    """Build the glyph outline drawing panel."""
    frame = ttk.Labelframe(parent, text=" Glyph Outline ", style="Section.TLabelframe")
    frame.pack(fill="both", expand=True)

    figure = Figure(figsize=(6, 5), dpi=100, facecolor="#ffffff")
    ax = figure.add_subplot(111)
    ax.set_aspect("equal")
    ax.axis("off")
    figure.tight_layout(pad=2)

    canvas = FigureCanvasTkAgg(figure, master=frame)
    canvas.get_tk_widget().pack(fill="both", expand=True)

    toolbar = NavigationToolbar2Tk(canvas, frame)
    toolbar.update()
    toolbar.pack(side="bottom", fill="x")

    return figure, ax, canvas


def build_data_panel(parent):
    """Build the right-side data panel, returning references to each sub-component."""
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

    info_labels = _build_basic_info(inner)
    metrics_tree = _build_geometry_table(inner)
    components_text = _build_components_info(inner)
    topology_text = _build_topology_info(inner)
    component_topology_text = _build_component_topology_info(inner)

    return info_labels, metrics_tree, components_text, topology_text, component_topology_text


def _build_basic_info(parent):
    f = ttk.Labelframe(parent, text=" Basic Info ", style="Section.TLabelframe", padding=8)
    f.pack(fill="x", pady=(0, 8))
    for i in range(4):
        f.columnconfigure(i, weight=1)

    info_labels = {}
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
        info_labels[key] = val

    return info_labels


def _build_geometry_table(parent):
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

    return tv


def _build_components_info(parent):
    f = ttk.Labelframe(parent, text=" Component Structure ", style="Section.TLabelframe", padding=6)
    f.pack(fill="x", pady=(0, 8))
    text = scrolledtext.ScrolledText(
        f, height=12, font=("Consolas", 10), relief="solid", bd=1, wrap="word"
    )
    text.pack(fill="both", expand=True)
    return text


def _build_topology_info(parent):
    f = ttk.Labelframe(parent, text=" Contour Topology ", style="Section.TLabelframe", padding=6)
    f.pack(fill="x", pady=(0, 8))
    text = scrolledtext.ScrolledText(
        f, height=4, font=("Consolas", 10), relief="solid", bd=1, wrap="word"
    )
    text.pack(fill="both", expand=True)
    return text


def _build_component_topology_info(parent):
    f = ttk.Labelframe(parent, text=" Component Topology ", style="Section.TLabelframe", padding=6)
    f.pack(fill="x", pady=(0, 8))
    text = scrolledtext.ScrolledText(
        f, height=5, font=("Consolas", 10), relief="solid", bd=1, wrap="word"
    )
    text.pack(fill="both", expand=True)
    return text

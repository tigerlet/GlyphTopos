import tkinter as tk
from tkinter import ttk


def build_toolbar(parent, font_var, char_var, show_outer, show_inner, show_points, show_fill,
                  on_pick_font, on_analyze, on_prev, on_next, on_refresh):
    """Build the top toolbar."""
    bar = ttk.Frame(parent)
    bar.pack(fill="x")

    ttk.Label(bar, text="Font file:", style="Key.TLabel").pack(side="left", padx=(0, 4))
    ttk.Entry(bar, textvariable=font_var, width=30).pack(side="left", padx=(0, 4))
    ttk.Button(bar, text="Browse…", command=on_pick_font).pack(side="left", padx=(0, 8))

    ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=6)

    ttk.Label(bar, text="Char / glyph name:", style="Key.TLabel").pack(side="left", padx=(0, 4))
    entry = ttk.Entry(bar, textvariable=char_var, width=16)
    entry.pack(side="left", padx=(0, 4))
    entry.bind("<Return>", lambda e: on_analyze())

    ttk.Button(bar, text="Analyze", style="Accent.TButton", command=on_analyze).pack(side="left", padx=(0, 4))
    ttk.Button(bar, text="Previous", command=on_prev).pack(side="left", padx=2)
    ttk.Button(bar, text="Next", command=on_next).pack(side="left", padx=2)

    ttk.Separator(bar, orient="vertical").pack(side="left", fill="y", padx=6)

    ttk.Label(bar, text="Show:", style="Key.TLabel").pack(side="left", padx=(0, 4))
    ttk.Checkbutton(bar, text="Outer", variable=show_outer, command=on_refresh).pack(side="left")
    ttk.Checkbutton(bar, text="Inner", variable=show_inner, command=on_refresh).pack(side="left")
    ttk.Checkbutton(bar, text="Vertices", variable=show_points, command=on_refresh).pack(side="left")
    ttk.Checkbutton(bar, text="Fill", variable=show_fill, command=on_refresh).pack(side="left")

from tkinter import ttk


def build_style():
    """Configure ttk styles."""
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

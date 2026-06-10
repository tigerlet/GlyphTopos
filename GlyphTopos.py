import tkinter as tk
import matplotlib
matplotlib.use("TkAgg")
from matplotlib import rcParams
import platform

if platform.system() == "Windows":
    rcParams["font.sans-serif"] = ["SimHei"]
elif platform.system() == "Darwin":
    rcParams["font.sans-serif"] = ["Arial Unicode MS"]
else:
    rcParams["font.sans-serif"] = ["WenQuanYi Zen Hei"]
rcParams["axes.unicode_minus"] = False

from glyph_analyzer import GlyphAnalyzerApp


def main():
    root = tk.Tk()
    app = GlyphAnalyzerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()

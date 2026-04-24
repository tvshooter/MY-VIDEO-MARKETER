#!/usr/bin/env python3
import os
import sys


def main():
    if sys.platform.startswith("linux") and not os.environ.get("DISPLAY"):
        print("ERROR: No display found ($DISPLAY not set). "
              "Run this app from a desktop session, not a headless terminal.")
        sys.exit(1)

    import customtkinter as ctk
    from video_trimmer.app import MainWindow

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("dark-blue")

    app = MainWindow()
    app.mainloop()


if __name__ == "__main__":
    main()

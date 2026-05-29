"""Headless GUI initialization smoke test.

This script intentionally does not start the Qt event loop forever. It proves
that dependency wiring, theme application, and MainWindow construction work in a
non-interactive environment.
"""

from __future__ import annotations

import os
import sys

# Must be set before QApplication is created. On Linux CI this avoids requiring
# an X server. On Windows it is harmless for this non-interactive smoke.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

from main import initialize_app
from src.ui.main_window import MainWindow
from src.ui.utils.theme import Theme, apply_theme


def main() -> None:
    app = QApplication(sys.argv)
    services = initialize_app()
    apply_theme(Theme(services["settings"].theme))
    window = MainWindow(services)
    window.show()
    app.processEvents()
    print("gui-smoke ok")
    print(f"ffmpeg {services['coordinator']._ffmpeg_path}")
    window.close()


if __name__ == "__main__":
    main()

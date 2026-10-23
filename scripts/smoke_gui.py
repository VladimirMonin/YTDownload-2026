"""Offscreen window construction/events/close, not visual or server acceptance."""

from __future__ import annotations

import sys

from scripts.smoke_support import close_services, isolated_smoke


def main() -> None:
    with isolated_smoke():
        from PySide6.QtCore import QCoreApplication, QEvent
        from PySide6.QtWidgets import QApplication

        from main import initialize_app
        from src.ui.main_window import MainWindow
        from src.ui.utils.theme import Theme, apply_theme

        app = QApplication(sys.argv)
        services = None
        window = None
        constructed = False
        try:
            services = initialize_app()
            apply_theme(Theme(services["settings"].theme))
            # Keep a reference even if __init__ fails after subscribing managers.
            window = MainWindow.__new__(MainWindow)
            window.__init__(services)
            constructed = True
            window.show()
            app.processEvents()
        finally:
            try:
                if window is not None:
                    try:
                        if constructed:
                            window.close()
                    finally:
                        for name in ("_download_manager", "_history_manager"):
                            manager = getattr(window, name, None)
                            if manager is not None:
                                manager.cleanup()
                        window.deleteLater()
                        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
            finally:
                try:
                    close_services(services)
                finally:
                    app.quit()
        print("gui-smoke ok")


if __name__ == "__main__":
    main()

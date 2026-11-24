"""نقطه ورود برنامه قیمت یار."""
from __future__ import annotations


def main() -> None:
    import sys

    from .ui.app_window import App

    application = App()
    if "--smoke" in sys.argv:
        application.after(1200, application.destroy)
    application.mainloop()


if __name__ == "__main__":
    main()

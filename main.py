import sys
from PySide6.QtWidgets import QApplication
from app.ui import MainWindow


def main(argv=None):
    """Main function to run the application or a worker subcommand."""
    argv = list(sys.argv[1:] if argv is None else argv)

    if argv and argv[0] == "--render-worker":
        from app.render_worker import main as render_worker_main

        return render_worker_main(argv[1:])

    app = QApplication([sys.argv[0], *argv])
    window = MainWindow()
    window.show()
    return app.exec()

if __name__ == "__main__":
    sys.exit(main())

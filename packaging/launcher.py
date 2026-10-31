"""Start the game from the downloadable build (PyInstaller runs this file)."""

from __future__ import annotations

import sys

from begin.__main__ import main

if __name__ == "__main__":
    sys.exit(main())

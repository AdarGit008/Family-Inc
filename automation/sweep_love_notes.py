"""
Family inc. — love-note sweep (V3.7). Hourly belt-and-suspenders behind the
server's lazy read-expiry: unlink every note past its 24h window even if no one
opened the dashboard to trigger the lazy path. Oneshot, run by
family-lovenote-sweep.timer (ENGINEERING §5).

Run:  uv run python automation/sweep_love_notes.py
"""
from __future__ import annotations

if __package__ in (None, ""):  # direct `python automation/sweep_love_notes.py`
    import sys as _sys
    from pathlib import Path as _Path
    _sys.path.insert(0, str(_Path(__file__).resolve().parent.parent))

import logging
from datetime import datetime

from automation.lib import config
from automation.love_note_server import sweep

log = logging.getLogger("lovenote.sweep")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    removed = sweep(config.LOVENOTE_STATE_DIR, datetime.now())
    log.info("love-note sweep: %d expired note(s) removed from %s",
             removed, config.LOVENOTE_STATE_DIR)


if __name__ == "__main__":
    main()

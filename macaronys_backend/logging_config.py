from __future__ import annotations

import logging

from macaronys_backend.config import settings


def configure_logging() -> None:
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )


logger = logging.getLogger("macaronys")

"""Minimal logger for the Playblast Plus Blender extension."""
import logging


class BlenderLogger:
    """Thin wrapper around stdlib logging."""

    LOGGER_NAME = "PlayblastPlus"
    FORMAT_DEFAULT = "[%(name)s][%(levelname)s] %(message)s"

    @classmethod
    def get(cls) -> logging.Logger:
        log = logging.getLogger(cls.LOGGER_NAME)
        if not log.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(cls.FORMAT_DEFAULT))
            log.addHandler(handler)
            log.propagate = False
        return log


log = BlenderLogger.get()

import os, logging
from logging.config import dictConfig

def configure_logging(service_name: str = "api"):
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    fmt = os.getenv("LOG_FORMAT", "plain").lower()

    dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "plain": {"format": "%(asctime)s %(levelname)s %(name)s %(message)s"},
            "json": {
                "class": "pythonjsonlogger.jsonlogger.JsonFormatter",
                "format": "%(asctime)s %(levelname)s %(name)s %(message)s %(pathname)s %(lineno)d %(process)d %(thread)d %(module)s",
            },
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "json" if fmt == "json" else "plain",
                "level": level,
            }
        },
        "loggers": {
                # uvicorn 등의 런타임 로거 포함
                "uvicorn": {"handlers": ["console"], "level": level, "propagate": False},
                "uvicorn.error": {"handlers": ["console"], "level": level, "propagate": False},
                "uvicorn.access": {"handlers": ["console"], "level": level, "propagate": False},
                "": {"handlers": ["console"], "level": level},
        },
    })
    logging.getLogger(__name__).info(f"logging configured for {service_name}")

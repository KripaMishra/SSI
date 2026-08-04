import json
import logging
import sys
import traceback

_RESERVED = {"args", "asctime", "created", "exc_info", "exc_text", "funcName",
             "levelno", "levelname", "message", "module", "msecs", "msg",
             "name", "pathname", "process", "processName", "relativeCreated",
             "stack_info", "thread", "threadName", "lineno", "filename", "taskName"}


class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_entry = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "script": record.pathname,
            "line": record.lineno,
            "message": record.getMessage(),
        }
        extra = {k: v for k, v in record.__dict__.items() if k not in _RESERVED}
        if extra:
            log_entry["extra"] = extra
        if record.exc_info and record.exc_info[0]:
            log_entry["traceback"] = traceback.format_exc().strip()
        return json.dumps(log_entry, ensure_ascii=False)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
    return logger
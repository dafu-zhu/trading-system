import atexit
import json
import logging
import logging.config
from pathlib import Path
from typing import override, Dict
import datetime


def setup_logging():
    """
    Configure logging from external JSON file.
    This should be called once at application startup.
    """
    # Get project root directory
    project_root = Path(__file__).parents[2]
    config_file = project_root / "src" / "logger" / "log_config.json"

    with open(config_file) as f_in:
        config = json.load(f_in)

    # Resolve log file paths relative to project root
    # This ensures logs are always written to the correct location
    for handler_name, handler_config in config.get("handlers", {}).items():
        if "filename" in handler_config:
            # Convert relative path to absolute path based on project root
            log_path = project_root / handler_config["filename"]
            log_path.parent.mkdir(parents=True, exist_ok=True)  # Create logs directory
            handler_config["filename"] = str(log_path)

    # Apply configuration
    logging.config.dictConfig(config)

    # For Python 3.12+: Start the queue listener
    # This creates a background thread that processes queued log records
    queue_handler = logging.getHandlerByName("queue_handler")
    if queue_handler is not None:
        queue_handler.listener.start()
        # Register cleanup function to stop listener on exit
        atexit.register(queue_handler.listener.stop)


class JsonFormatter(logging.Formatter):

    LOG_RECORD_BUILTIN_ATTRS = {
        "args", "asctime", "created", "exc_info", "exc_text", "filename", "funcName",
        "levelname", "levelno", "lineno", "module", "msecs", "message", "msg", "name",
        "pathname", "process", "processName", "relativeCreated", "stack_info", "thread",
        "threadName", "taskName",
    }

    def __init__(self, *, fmt_keys: Dict[str, str] | None) -> None:
        super().__init__()
        self.fmt_keys = fmt_keys if fmt_keys is not None else {}

    @override
    def format(self, record: logging.LogRecord):
        message = self._log_dict(record)
        return json.dumps(message, default=str)

    def _log_dict(self, record: logging.LogRecord):
        """Build the dictionary that will be converted to JSON."""

        # These fields are always included
        always_fields = {
            "message": record.getMessage(),
            "timestamp": datetime.datetime.fromtimestamp(
                record.created, tz=datetime.timezone.utc
            ).isoformat(),
        }

        # Add exception info if this is an error log
        if record.exc_info is not None:
            always_fields["exc_info"] = self.formatException(record.exc_info)

        # Add stack trace if requested
        if record.stack_info is not None:
            always_fields["stack_info"] = self.formatStack(record.stack_info)

        # Map configured fields (e.g., "level" -> record.levelname)
        # Uses walrus operator for efficiency
        message = {
            key: msg_val
            if (msg_val := always_fields.pop(val, None)) is not None
            else getattr(record, val)
            for key, val in self.fmt_keys.items()
        }

        # Add back any always_fields that weren't mapped
        message.update(always_fields)

        # Add custom fields from extra parameter
        # e.g., logger.info("msg", extra={"user_id": 123})
        for key, val in record.__dict__.items():
            if key not in self.LOG_RECORD_BUILTIN_ATTRS:
                message[key] = val

        return message


if __name__ == '__main__':
    logger = logging.getLogger(__name__)
    setup_logging()

    # Example usage
    logger.debug("debug message", extra={"x": "hello"})
    logger.info("info message")
    logger.warning("warning message")
    logger.error("error message")
    logger.critical("critical message")

    # Exception logging
    try:
        1 / 0
    except ZeroDivisionError:
        logger.exception("exception message")
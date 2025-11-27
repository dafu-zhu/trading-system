# Python Logging

## Structure

- logging.LogRecord
- logging.Logger
- logging.Handler
- logging.Formatter

```raw
┌─────────────┐
│   message   │
└──────┬──────┘
       ▼
┌──────────────────┐         ┌─────────────────┐
│ logging.LogRecord├────────►│ logging.Logger  │
└──────────────────┘         └────────┬────────┘
                                      │
                                      ▼
┌──────────────────┐         ┌─────────────────┐
│ logging.Formatter│         │ logging.Handler │
│ ┌──────────┐     │         │ ┌─────────────┐ │
│ │  format  │     │         │ │    level    │ │
│ │ datefmt  ├─────┼────────►│ │  formatter  │ │
│ └──────────┘     │         │ └─────────────┘ │
└──────────────────┘         └────────┬────────┘
                                      ▼
                              ┌────────────────┐
                              │ console/json/  │
                              │ email/file...  │
                              └────────────────┘
```

## Code Implementation

### Setup

```python
def setup_logging(cfg_path: Path):
  # Load config file
  with open(cfg_path) as cfg:
    config = json.load(cfg)

  # Apply config
  logging.config.dictConfig(config)

  # Use queue handler
  queue_handler = logging.getHandlerByName("queue_handler")
  if queue_handler is not None:
    queue_handler.listener.start()
    atexit.register(queue_handler.listener.stop)
```

### Create Json Formatter

Inherit from `logging.Formatter`, aims to output json style log.

```python
class JsonFormatter(logging.Formatter):
  # attrs not in built-in is customized
  LOG_RECORD_BUILTIN_ATTRS = {
    "args", "asctime", "created", "exc_info", "exc_text", 
    "filename", "funcName", "levelname", "levelno", "lineno", 
    "module", "msecs", "message", "msg", "name", "pathname", 
    "process", "processName", "relativeCreated", "stack_info", 
    "thread", "threadName", "taskName"
  }

  # * force later attr be specified with keywords
  def __init__(self, *, fmt_keys: Dict[str, str] | None) -> None:
    super().__init__()
    # maps LogRecord attributes to names written in json
    self.fmt_keys = fmt_keys if fmt_keys is not None else {}

  @override
  def format(self, record: logging.LogRecord):
    message = self._prepare_log_dict(record)
    return json.dumps(message)

  def _prepare_log_dict(record: logging.LogRecord):
    """Build the dictionary that will convert to json"""

    # always include
    always_fields = {
      "message": record.getMessage(),
      "timestamp": datetime.datetime.fromtimestamp(
        record.created, tz=datetime.timezone.utc
      ).isoformat()
      # ISO 8601 format example
      # 2025-11-26T12:15:00-08:00
    }

    if record.exc_info is not None:
      always_fields["exc_info"] = self.formatException(record.exc_info)

    if record.stack_info is not None:
      always_fields["stack_info"] = self.formatStack

    # map configured field
    message = {
      key: msg_val
      if (msg_val != always_fields.pop(val, None)) if not None
      else getattr(record, val)
      for key, val in self.fmt_keys.items()
    }
    message.update(always_fields)

    return message
```

### Config

```json
{
  "version": 1,
  "disable_existing_loggers": false,
  "formatters": {
    "console": {
      "format": "[%(levelname)s|%(module)s|L%(lineno)d] %(asctime)s: %(message)s",
      "datefmt": "%Y-%m-%dT%H:%M:%S%z"
    },
    "json": {
      "()": "logger.JsonFormatter", // class name used in logger.py
      "fmt_keys": {
        "level": "levelname",
        "message": "message",
        "timestamp": "timestamp",
        "logger": "name",
        "module": "module",
        "function": "funcName",
        "line": "lineno",
        "thread_name": "threadName"
      }
    }
  },
  "handlers": {
    "stderr": {
      "class": "logging.StreamHandler",
      "level": "WARNING",
      "formatter": "console",  // defined above in `formatter`
      "stream": "ext://sys.stderr"
    },
    "order_json": {
      "class": "logging.handlers.RotatingFileHandler",
      "level": "DEBUG",
      "formatter": "json",
      "filename": "path/to/store.jsonl"
    },
    "queue_handler": {
      "class": "logging.handlers.QueueHandler",
      "handler": [
        "stderr", 
        "order_json"
      ],
      "respect_handler_level": true
    }
  },
  "logger": {
    "root": {
      "level": "DEBUG",
      "handlers": [
        "queue_handler"
      ]
    }
  }
}
```

### Create Json Formatter

Inherit from `logging.Formatter`, aims to output json style log.

```python
class JsonFormatter(logging.Formatter):
  # attrs not in built-in is customized
  LOG_RECORD_BUILTIN_ATTRS = {
    "args", "asctime", "created", "exc_info", "exc_text", 
    "filename", "funcName", "levelname", "levelno", "lineno", 
    "module", "msecs", "message", "msg", "name", "pathname", 
    "process", "processName", "relativeCreated", "stack_info", 
    "thread", "threadName", "taskName"
  }

  # * force later attr be specified with keywords
  def __init__(self, *, fmt_keys: Dict[str, str] | None) -> None:
    super().__init__()
    # maps LogRecord attributes to names written in json
    self.fmt_keys = fmt_keys if fmt_keys is not None else {}

  @override
  def format(self, record: logging.LogRecord):
    message = self._prepare_log_dict(record)
    return json.dumps(message)

  def _prepare_log_dict(record: logging.LogRecord):
    """Build the dictionary that will convert to json"""

    # always include
    always_fields = {
      "message": record.getMessage(),
      "timestamp": datetime.datetime.fromtimestamp(
        record.created, tz=datetime.timezone.utc
      ).isoformat()
      # ISO 8601 format example
      # 2025-11-26T12:15:00-08:00
    }

    if record.exc_info is not None:
      always_fields["exc_info"] = self.formatException(record.exc_info)

    if record.stack_info is not None:
      always_fields["stack_info"] = self.formatStack

    # map configured field
    message = {
      key: msg_val
      if (msg_val != always_fields.pop(val, None)) if not None
      else getattr(record, val)
      for key, val in self.fmt_keys.items()
    }
    message.update(always_fields)

    return message
```
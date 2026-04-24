"""Logging helpers used across the API.

Today this is intentionally lightweight. In production it can be replaced with
structured logging to a central sink without changing route code.
"""

import json
import logging
import sys
from datetime import datetime


logger = logging.getLogger('agri_marketplace')
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter('%(message)s'))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)


def log_event(event: str, **kwargs) -> None:
    payload = {'timestamp': datetime.utcnow().isoformat(), 'event': event, **kwargs}
    logger.info(json.dumps(payload, default=str))

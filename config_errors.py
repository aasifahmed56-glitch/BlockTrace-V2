"""
Wording for features that need a secret the server host hasn't configured.

These messages reach the UI unchanged, so they are written for whoever is using
the app. The name of the missing setting goes to the server log instead, where
the operator will look for it.
"""

import logging

logger = logging.getLogger(__name__)


def not_configured(feature, setting):
    """Logs which setting is missing and returns a visitor-facing message."""
    logger.warning("%s is unavailable: %s is not set on the server.", feature, setting)
    return f"{feature} isn't set up on this server yet, so this action is unavailable for now."


def rejected_credentials(service, setting):
    """Logs that the configured credential was refused and returns a visitor-facing message."""
    logger.warning("%s rejected the configured %s (HTTP 401).", service, setting)
    return f"{service} refused this server's credentials, so this action is unavailable for now."

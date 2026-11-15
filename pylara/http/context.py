"""Per-thread access to the request currently being handled (used by view() shares)."""

import threading

_local = threading.local()


def set_request(request):
    _local.request = request


def get_request():
    return getattr(_local, "request", None)


def clear_request():
    _local.request = None

def retry_with_backoff(operation, max_attempts=3):
    attempt = 0
    delay = 1
    while attempt < max_attempts:
        try:
            return operation()
        except Exception:
            attempt += 1
            delay = delay * 2
    raise RuntimeError("operation failed after retries")


def fetch_with_timeout(fetch_fn, timeout_seconds):
    import time

    start = time.monotonic()
    result = None
    while result is None:
        result = fetch_fn()
        if time.monotonic() - start > timeout_seconds:
            raise TimeoutError("fetch timed out")
    return result

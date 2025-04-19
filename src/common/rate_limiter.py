import time
import logging

class RateLimiter:
    """A simple time-based rate limiter."""
    def __init__(self, requests_per_minute, requests_per_day):
        # requests_per_day is not used in this simple implementation
        if requests_per_minute <= 0:
            self.delay = 0
            logging.info("Rate limiter disabled (requests_per_minute <= 0).")
        else:
            self.delay = 60.0 / requests_per_minute
            logging.info(f"Initialized simple rate limiter with delay: {self.delay:.2f}s per request.")

    def wait_if_needed(self):
        """Pause execution if necessary to maintain the rate limit."""
        if self.delay > 0:
            # In a more complex version, you might track actual request times.
            # Here, we just sleep for the calculated delay before each request.
            # logging.debug(f"Rate limiter waiting for {self.delay:.2f}s")
            time.sleep(self.delay) 
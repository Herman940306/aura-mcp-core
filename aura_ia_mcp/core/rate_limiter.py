"""Rate limiting using token bucket algorithm."""

import time


class TokenBucket:
    """Token bucket rate limiter."""

    def __init__(self, capacity: int, refill_rate: float):
        """
        Initialize token bucket.

        Args:
            capacity: Maximum number of tokens
            refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.time()

    def consume(self, tokens: int = 1) -> bool:
        """
        Try to consume tokens.

        Returns:
            True if tokens were consumed, False if not enough tokens
        """
        self._refill()

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill

        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now


class RateLimiter:
    """Rate limiter with per-key buckets."""

    def __init__(self, capacity: int = 100, refill_rate: float = 10.0):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.buckets: dict[str, TokenBucket] = {}

    def is_allowed(self, key: str, tokens: int = 1) -> bool:
        """
        Check if request is allowed for the given key.

        Args:
            key: Identifier (e.g., user ID, IP address)
            tokens: Number of tokens to consume

        Returns:
            True if allowed, False if rate limited
        """
        if key not in self.buckets:
            self.buckets[key] = TokenBucket(self.capacity, self.refill_rate)

        return self.buckets[key].consume(tokens)

    def get_remaining(self, key: str) -> int:
        """Get remaining tokens for a key."""
        if key not in self.buckets:
            return self.capacity

        self.buckets[key]._refill()
        return int(self.buckets[key].tokens)

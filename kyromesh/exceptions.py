"""Exception classes for Kyromesh SDK."""


class KyromeshError(Exception):
    """Base exception for all Kyromesh SDK errors."""
    
    def __init__(self, message: str, code: str = "unknown_error") -> None:
        """
        Initialize KyromeshError.
        
        Args:
            message: Error message
            code: Error code from API response
        """
        self.message = message
        self.code = code
        super().__init__(message)


class AuthError(KyromeshError):
    """Raised when authentication fails (401)."""
    
    def __init__(self, message: str = "Authentication failed") -> None:
        super().__init__(message, "auth_error")


class QuotaExceededError(KyromeshError):
    """Raised when quota is exceeded (429)."""
    
    def __init__(
        self,
        message: str = "Quota exceeded",
        jobs_remaining: int = 0,
        retry_after: int = 0,
    ) -> None:
        super().__init__(message, "quota_exceeded")
        self.jobs_remaining = jobs_remaining
        self.retry_after = retry_after


class GuardBlockedError(KyromeshError):
    """Raised when Guard blocks a job (400 from guard)."""
    
    def __init__(
        self,
        message: str = "Guard blocked the request",
        block_reason: str = "",
    ) -> None:
        super().__init__(message, "guard_blocked")
        self.block_reason = block_reason


class ProviderError(KyromeshError):
    """Raised when provider returns an error."""
    
    def __init__(
        self,
        message: str = "Provider error",
        provider: str = "",
        status_code: int = 0,
    ) -> None:
        super().__init__(message, "provider_error")
        self.provider = provider
        self.status_code = status_code


class TimeoutError(KyromeshError):
    """Raised when operation times out."""
    
    def __init__(
        self,
        message: str = "Operation timed out",
        timeout_seconds: int = 0,
    ) -> None:
        super().__init__(message, "timeout_error")
        self.timeout_seconds = timeout_seconds

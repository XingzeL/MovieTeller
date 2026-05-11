class FramePoolError(RuntimeError):
    """Base error for frame-pool operations."""


class PoolManifestError(FramePoolError):
    """Raised when manifest/shots files are missing or invalid."""


class PoolWindowMiss(FramePoolError):
    """Raised when a query window has no matching frames in the pool."""

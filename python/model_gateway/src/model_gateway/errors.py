class GatewayError(Exception):
    pass


class GatewayConfigError(GatewayError):
    pass


class GatewayAuthError(GatewayError):
    pass


class GatewayRateLimitError(GatewayError):
    pass


class GatewayTimeoutError(GatewayError):
    pass


class GatewayTransientError(GatewayError):
    pass


class GatewayProviderError(GatewayError):
    pass


class GatewayUnsupportedCapabilityError(GatewayError):
    pass

"""Custom exception types shared across the TerraShift modules."""


class DataDiscoveryError(Exception):
    """Raised when authentication or CMR granule search fails."""


class DataAccessError(Exception):
    """Raised when loading data from OPeNDAP fails."""


class InsufficientDataError(ValueError):
    """Raised when there are too few valid data points for trend analysis."""


class ConfigError(Exception):
    """Raised when the static configuration is inconsistent."""

import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from src.config.settings import settings

def init_sentry() -> None:
    """Initializes Sentry if a valid DSN is provided."""
    if settings.sentry_dsn:
        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            integrations=[FastApiIntegration()],
            traces_sample_rate=1.0,
            profiles_sample_rate=1.0,
        )

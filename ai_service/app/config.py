"""Service configuration — environment-driven, no secrets stored here.

The service itself is credential-less: the caller's Posterra API key and
target app key are forwarded verbatim on every Odoo call (env vars in stdio
mode, HTTP headers in remote mode). The only required setting is where the
Odoo gateway lives.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    odoo_base_url: str = "http://localhost:8069"
    request_timeout_seconds: float = 60.0
    port: int = 8808
    log_level: str = "INFO"

    model_config = {"env_prefix": "", "env_file": ".env", "extra": "ignore"}


settings = Settings()

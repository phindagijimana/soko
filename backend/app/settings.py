"""Environment-driven application settings.

All runtime knobs should be configured here instead of being scattered across
route handlers or utility modules.
"""


from pathlib import Path

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


def _default_allowed_origins() -> str:
    """Local dev: Vite on 2000-2050 (see ./soko) or legacy 5173."""
    parts = ['http://127.0.0.1:5173', 'http://localhost:5173']
    for port in range(2000, 2051):
        parts.append(f'http://127.0.0.1:{port}')
        parts.append(f'http://localhost:{port}')
    return ','.join(parts)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file='.env', env_file_encoding='utf-8', extra='ignore')

    app_name: str = 'Agri Marketplace API'
    environment: str = 'development'
    debug: bool = True
    secret_key: str = 'change-me-in-production'

    database_url: str = f"sqlite:///{(BASE_DIR / 'agri_marketplace.db').as_posix()}"
    allowed_origins: str = Field(default_factory=_default_allowed_origins)
    trusted_hosts: str = '127.0.0.1,localhost,testserver'

    sms_provider: str = 'file'
    sms_log_path: str = str(BASE_DIR / 'sms_log.txt')
    twilio_account_sid: str = 'placeholder'
    twilio_auth_token: str = 'placeholder'
    twilio_from_phone: str = '+10000000000'
    sms_status_callback_url: str = 'placeholder'

    otp_length: int = 6
    otp_expiry_minutes: int = 5
    otp_max_attempts: int = 5
    otp_lockout_minutes: int = 15
    otp_resend_cooldown_seconds: int = 30
    auth_token_hours: int = 24

    rate_limit_window_seconds: int = 60
    rate_limit_max_requests: int = 30
    auth_rate_limit_max_requests: int = 8
    upload_rate_limit_max_requests: int = 12

    upload_dir: str = str(BASE_DIR / 'uploads')
    max_upload_size_bytes: int = 2 * 1024 * 1024
    max_image_count_per_listing: int = 3
    enable_seed_data: bool = True

    admin_phone_numbers: str = '+250700000001'
    support_email: str = 'support@example.com'

    # When false, tables must exist (e.g. Alembic upgrade already ran).
    create_tables_on_startup: bool = True

    # local | s3 — S3-compatible (AWS S3, MinIO, R2) via boto3
    storage_backend: str = 'local'
    s3_bucket_name: str = ''
    aws_region: str = 'us-east-1'
    aws_access_key_id: str = ''
    aws_secret_access_key: str = ''
    aws_endpoint_url: str = ''  # e.g. http://127.0.0.1:9000 for MinIO
    # Public base URL for browser <img src> (no trailing slash), e.g. https://cdn.example.com/media
    media_public_base_url: str = ''

    sentry_dsn: str = ''

    @model_validator(mode='after')
    def storage_settings_consistent(self):
        if self.storage_backend == 's3':
            if not self.s3_bucket_name.strip():
                raise ValueError('S3_BUCKET_NAME is required when STORAGE_BACKEND=s3')
            if not self.media_public_base_url.strip():
                raise ValueError('MEDIA_PUBLIC_BASE_URL is required when STORAGE_BACKEND=s3')
        return self

    @property
    def allowed_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(',') if origin.strip()]

    @property
    def admin_phone_list(self) -> list[str]:
        return [phone.strip() for phone in self.admin_phone_numbers.split(',') if phone.strip()]

    @property
    def trusted_host_list(self) -> list[str]:
        return [host.strip() for host in self.trusted_hosts.split(',') if host.strip()]


settings = Settings()

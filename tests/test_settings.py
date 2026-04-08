from app.platform.config.settings import AppSettings


def test_settings_defaults() -> None:
    settings = AppSettings()
    assert settings.app_name
    assert settings.db_url

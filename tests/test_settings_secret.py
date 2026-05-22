import settings


def test_secret_settings_constants_exist_with_expected_types() -> None:
    assert isinstance(settings.SECRET_WORD_PREFIXES, tuple)
    assert all(isinstance(p, str) for p in settings.SECRET_WORD_PREFIXES)

    assert isinstance(settings.SECRET_MASK_GLYPHS, int)
    assert isinstance(settings.SECRET_MASK_CHAR, str)
    assert isinstance(settings.SECRET_HIDE_ON_FOCUS_OUT, bool)
    assert isinstance(settings.SECRET_REVEAL_INACTIVITY_MS, int)


def test_secret_settings_defaults() -> None:
    assert settings.SECRET_WORD_PREFIXES == (
        "passw",
        "auth",
        "token",
        "key",
        "secret",
        "private",
        "cert",
    )
    assert settings.SECRET_MASK_GLYPHS == 8
    assert settings.SECRET_MASK_CHAR == "•"
    assert settings.SECRET_HIDE_ON_FOCUS_OUT is True
    assert settings.SECRET_REVEAL_INACTIVITY_MS == 0

from validation.secret_names import name_looks_secret

DEFAULT_PREFIXES = ("passw", "auth", "token", "key", "secret", "private", "cert")


def test_password_matches_passw_prefix() -> None:
    assert name_looks_secret("Password", DEFAULT_PREFIXES)


def test_user_token_v2_matches_token_word() -> None:
    assert name_looks_secret("user_token_v2", DEFAULT_PREFIXES)


def test_private_key_matches_private_or_key_word_prefix() -> None:
    assert name_looks_secret("private_key", DEFAULT_PREFIXES)


def test_certificate_matches_cert_prefix() -> None:
    assert name_looks_secret("certificate", DEFAULT_PREFIXES)


def test_my_api_key_matches_camel_case_key_word() -> None:
    assert name_looks_secret("myApiKey", DEFAULT_PREFIXES)


def test_description_does_not_match() -> None:
    assert not name_looks_secret("description", DEFAULT_PREFIXES)


def test_keynote_matches_key_prefix_by_design() -> None:
    assert name_looks_secret("keynote", DEFAULT_PREFIXES)

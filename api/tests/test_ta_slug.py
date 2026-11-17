from app.core.ta_slug import TA_SLUG_OVERRIDES, ta_slug


def test_plain_names_drop_spaces_only():
    assert ta_slug("Aryna Sabalenka") == "ArynaSabalenka"
    assert ta_slug("Gael Monfils") == "GaelMonfils"


def test_overrides_win_over_the_plain_rule():
    assert ta_slug("Felix Auger-Aliassime") == "FelixAugerAliassime"
    assert ta_slug("Catherine McNally") == "CatyMcnally"
    assert all(ta_slug(name) == slug for name, slug in TA_SLUG_OVERRIDES.items())

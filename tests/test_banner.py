from agent.tui.banner import build_welcome_markup, os_banner


def test_os_banner_non_empty() -> None:
    assert len(os_banner().strip()) > 10


def test_welcome_contains_nyx_and_cohere() -> None:
    text = build_welcome_markup()
    assert "Nyx" in text
    assert "Cohere" in text
    assert "Rzy" in text

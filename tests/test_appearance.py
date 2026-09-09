"""Tests for the reading comfort settings and the user config writer.

The CSS generator and the config writer are pure enough to test directly; the Streamlit
panel is not, and is covered by running the app.

Persistence is the part worth guarding. The read side of the user config has existed since
the beginning and nothing ever wrote it, so this is new machinery — and a save that drops
the model download overrides, or that truncates the file mid-write, breaks something the
user cannot easily diagnose.
"""

from __future__ import annotations

import yaml

from src.ui.appearance import (
    DEFAULT_FONT_SIZE_PX,
    DEFAULT_LINE_HEIGHT,
    FONT_SIZE_RANGE,
    LINE_HEIGHT_RANGE,
    Appearance,
    build_css,
)


class TestAppearanceModel:
    def test_defaults_are_streamlit_neutral(self):
        # A product decision: the application offers a dyslexia-friendly view, it does not
        # impose one. If these change, the first-run experience changes with them.
        assert Appearance().font_size_px == DEFAULT_FONT_SIZE_PX == 16
        assert Appearance().line_height == DEFAULT_LINE_HEIGHT == 1.6
        assert Appearance().focus_mode is False

    def test_the_default_line_height_meets_wcag_1_4_12(self):
        assert DEFAULT_LINE_HEIGHT >= 1.5

    def test_reads_stored_settings(self):
        cfg = {"ui": {"appearance": {"font_size_px": 22, "line_height": 2.0, "focus_mode": True}}}
        stored = Appearance.from_config(cfg)
        assert stored.font_size_px == 22
        assert stored.line_height == 2.0
        assert stored.focus_mode is True

    def test_missing_config_falls_back_to_defaults(self):
        assert Appearance.from_config({}) == Appearance()
        assert Appearance.from_config({"ui": {}}) == Appearance()
        assert Appearance.from_config({"ui": {"appearance": {}}}) == Appearance()

    def test_a_partial_config_keeps_the_other_defaults(self):
        stored = Appearance.from_config({"ui": {"appearance": {"font_size_px": 20}}})
        assert stored.font_size_px == 20
        assert stored.line_height == DEFAULT_LINE_HEIGHT

    def test_is_default_detects_an_untouched_configuration(self):
        assert Appearance().is_default()
        assert not Appearance(font_size_px=22).is_default()

    def test_the_defaults_sit_inside_the_offered_ranges(self):
        assert FONT_SIZE_RANGE[0] <= DEFAULT_FONT_SIZE_PX <= FONT_SIZE_RANGE[1]
        assert LINE_HEIGHT_RANGE[0] <= DEFAULT_LINE_HEIGHT <= LINE_HEIGHT_RANGE[1]


class TestCss:
    def test_font_size_is_set_on_the_root(self):
        # Streamlit sizes everything in rem, so the root override scales widgets and body
        # text together. Setting it per element would miss most of the interface.
        assert "html { font-size: 22px; }" in build_css(Appearance(font_size_px=22))

    def test_line_height_reaches_the_text_area_too(self):
        css = build_css(Appearance(line_height=2.1))
        assert "line-height: 2.1" in css
        assert "textarea" in css

    def test_focus_mode_hides_the_chrome_and_the_sidebar(self):
        css = build_css(Appearance(focus_mode=True))
        for target in ("stHeader", "stToolbar", "stMainMenu", "stSidebar"):
            assert target in css

    def test_focus_mode_ships_its_own_exit_affordance(self):
        """Verified in the browser: hiding the sidebar with display:none leaves Streamlit
        believing it is still expanded, so it never renders its own collapsed control. Focus
        mode must therefore provide the way back itself, or the user is stranded with the
        settings hidden and no route to them."""
        from src.ui.content import Content

        assert Content.APPEARANCE_FOCUS_EXIT
        assert "stSidebarCollapsedControl" not in build_css(Appearance(focus_mode=True))

    def test_chrome_is_visible_when_focus_mode_is_off(self):
        assert "stHeader" not in build_css(Appearance(focus_mode=False))

    def test_the_output_is_a_style_element(self):
        css = build_css(Appearance())
        assert css.startswith("<style>") and css.endswith("</style>")


class TestSaveUserConfig:
    """The writer that did not exist until now."""

    @staticmethod
    def _patched(tmp_path, monkeypatch):
        import src.utils.config as config_module

        target = tmp_path / "config.yaml"
        monkeypatch.setattr(config_module, "get_user_config_path", lambda **_: target)
        return config_module, target

    def test_writes_a_new_file(self, tmp_path, monkeypatch):
        config_module, target = self._patched(tmp_path, monkeypatch)
        config_module.save_user_config({"ui": {"appearance": {"font_size_px": 20}}})
        assert yaml.safe_load(target.read_text(encoding="utf-8")) == {
            "ui": {"appearance": {"font_size_px": 20}}
        }

    def test_merges_instead_of_replacing(self, tmp_path, monkeypatch):
        """The same file carries the model download overrides; a save must not drop them."""
        config_module, target = self._patched(tmp_path, monkeypatch)
        target.write_text(
            yaml.safe_dump({"llm": {"downloads": [{"id": "mistral-7b-q4"}]}}), encoding="utf-8"
        )

        config_module.save_user_config({"ui": {"appearance": {"font_size_px": 20}}})

        saved = yaml.safe_load(target.read_text(encoding="utf-8"))
        assert saved["llm"]["downloads"] == [{"id": "mistral-7b-q4"}]
        assert saved["ui"]["appearance"]["font_size_px"] == 20

    def test_merges_within_a_nested_section(self, tmp_path, monkeypatch):
        config_module, target = self._patched(tmp_path, monkeypatch)
        config_module.save_user_config({"ui": {"appearance": {"font_size_px": 20}}})
        config_module.save_user_config({"ui": {"appearance": {"line_height": 2.0}}})

        saved = yaml.safe_load(target.read_text(encoding="utf-8"))
        assert saved["ui"]["appearance"] == {"font_size_px": 20, "line_height": 2.0}

    def test_leaves_no_temporary_file_behind(self, tmp_path, monkeypatch):
        config_module, target = self._patched(tmp_path, monkeypatch)
        config_module.save_user_config({"ui": {"appearance": {"font_size_px": 20}}})
        assert not list(tmp_path.glob("*.tmp"))

    def test_the_result_round_trips_through_load(self, tmp_path, monkeypatch):
        config_module, target = self._patched(tmp_path, monkeypatch)
        config_module.save_user_config(
            {"ui": {"appearance": {"font_size_px": 24, "line_height": 2.2, "focus_mode": True}}}
        )
        stored = Appearance.from_config(yaml.safe_load(target.read_text(encoding="utf-8")))
        assert stored == Appearance(font_size_px=24, line_height=2.2, focus_mode=True)


class TestDiffRendering:
    """The diff used to hardcode typography, overriding every reading setting."""

    @staticmethod
    def _diff(appearance=None):
        from src.ui.layout import _generate_html_diff

        return _generate_html_diff("Le chat dort.", "Le chien dort.", appearance)

    def test_no_longer_pins_the_font(self):
        assert "font-family" not in self._diff()
        assert "font-size" not in self._diff()

    def test_honours_the_reader_line_height(self):
        assert "line-height: 2.3" in self._diff(Appearance(line_height=2.3))

    def test_additions_are_underlined_not_bold(self):
        # E6: underline survives a high-contrast theme and does not rely on colour alone.
        diff = self._diff()
        assert "text-decoration: underline" in diff
        assert "<strong" not in diff

    def test_deletions_keep_the_strikethrough_at_full_contrast(self):
        diff = self._diff()
        assert "line-through" in diff
        assert "opacity" not in diff

"""Tests for PhoneticLabel."""


from parla.ui.widgets.phonetic_label import PhoneticLabel, PhoneticWord


def _sample_words() -> list[PhoneticWord]:
    return [
        PhoneticWord(text="Hello", phonetic="/hɛˈloʊ/"),
        PhoneticWord(text="world", phonetic="/wɜːrld/"),
        PhoneticWord(text="today", phonetic="/təˈdeɪ/"),
    ]


class TestPhoneticLabel:
    def test_set_words(self, qtbot):
        widget = PhoneticLabel()
        qtbot.addWidget(widget)
        widget.set_words(_sample_words())
        assert len(widget._words) == 3

    def test_phonetic_visible_default(self, qtbot):
        widget = PhoneticLabel()
        qtbot.addWidget(widget)
        assert widget.is_phonetic_visible is True

    def test_phonetic_toggle_off(self, qtbot):
        widget = PhoneticLabel()
        qtbot.addWidget(widget)
        widget.set_phonetic_visible(False)
        assert widget.is_phonetic_visible is False

    def test_phonetic_toggle_on(self, qtbot):
        widget = PhoneticLabel()
        qtbot.addWidget(widget)
        widget.set_phonetic_visible(False)
        widget.set_phonetic_visible(True)
        assert widget.is_phonetic_visible is True

    def test_highlight_word(self, qtbot):
        widget = PhoneticLabel()
        qtbot.addWidget(widget)
        widget.set_words(_sample_words())
        widget.highlight_word(1)
        assert widget.highlighted_index == 1

    def test_clear_highlight(self, qtbot):
        widget = PhoneticLabel()
        qtbot.addWidget(widget)
        widget.set_words(_sample_words())
        widget.highlight_word(1)
        widget.clear_highlight()
        assert widget.highlighted_index is None

    def test_highlight_out_of_range_is_noop(self, qtbot):
        widget = PhoneticLabel()
        qtbot.addWidget(widget)
        widget.set_words(_sample_words())
        widget.highlight_word(999)
        assert widget.highlighted_index is None

    def test_highlight_negative_is_noop(self, qtbot):
        widget = PhoneticLabel()
        qtbot.addWidget(widget)
        widget.set_words(_sample_words())
        widget.highlight_word(-1)
        assert widget.highlighted_index is None

    def test_set_words_clears_highlight(self, qtbot):
        widget = PhoneticLabel()
        qtbot.addWidget(widget)
        widget.set_words(_sample_words())
        widget.highlight_word(0)
        widget.set_words(_sample_words())
        assert widget.highlighted_index is None

    def test_paint_with_phonetic_no_crash(self, qtbot):
        widget = PhoneticLabel()
        qtbot.addWidget(widget)
        widget.set_words(_sample_words())
        widget.show()
        qtbot.waitExposed(widget)

    def test_paint_without_phonetic_no_crash(self, qtbot):
        widget = PhoneticLabel()
        qtbot.addWidget(widget)
        widget.set_words(_sample_words())
        widget.set_phonetic_visible(False)
        widget.show()
        qtbot.waitExposed(widget)

    def test_empty_words_no_crash(self, qtbot):
        widget = PhoneticLabel()
        qtbot.addWidget(widget)
        widget.set_words([])
        widget.show()
        qtbot.waitExposed(widget)

    def test_paint_with_highlight_no_crash(self, qtbot):
        widget = PhoneticLabel()
        qtbot.addWidget(widget)
        widget.set_words(_sample_words())
        widget.highlight_word(2)
        widget.show()
        qtbot.waitExposed(widget)

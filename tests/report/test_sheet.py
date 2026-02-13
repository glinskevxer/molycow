import pytest

from molycow.report.sheet import Section, Sheet


def test_a_section_with_rows_indents_them() -> None:
    section = Section("doses", ("DS-250408-01 22.0 mCi",))
    assert section.lines() == ["doses", "  DS-250408-01 22.0 mCi"]
    assert not section.is_empty


def test_an_empty_section_says_what_nothing_means() -> None:
    section = Section("doses", (), "nothing was drawn")
    assert section.is_empty
    assert section.lines() == ["doses", "  nothing was drawn"]


def test_an_empty_section_falls_back_to_a_plain_word() -> None:
    assert Section("doses").lines()[1] == "  nothing"


def test_a_sheet_underlines_its_title() -> None:
    sheet = Sheet("day sheet", (Section("doses", ("one",)),))
    lines = sheet.lines()
    assert lines[0] == "day sheet"
    assert lines[1] == "=" * len("day sheet")
    assert lines[2] == ""
    assert lines[3] == "doses"


def test_a_sheet_finds_its_sections_by_title() -> None:
    sheet = Sheet("day sheet", (Section("doses", ("one",)), Section("waste")))
    assert sheet.has("waste")
    assert not sheet.has("gossip")
    assert sheet.section("doses").rows == ("one",)
    with pytest.raises(KeyError):
        sheet.section("gossip")


def test_a_sheet_counts_its_rows_and_prints_as_text() -> None:
    sheet = Sheet("day sheet", (Section("doses", ("one", "two")), Section("waste")))
    assert sheet.row_count == 2
    assert sheet.text().splitlines()[0] == "day sheet"


def test_a_sheet_with_no_sections_is_just_a_heading() -> None:
    assert Sheet("day sheet").lines() == ["day sheet", "========="]

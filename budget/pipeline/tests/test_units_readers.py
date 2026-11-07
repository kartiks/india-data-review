"""readers.py on small hand-made files: footnote markers are dropped before a number can absorb them, cells are
cleaned the same way in every format, and spreadsheet numbers read as printed."""

import openpyxl
import pytest

from budget_pipeline.readers import NUM_TOKEN, drop_small_chars, read_any, read_html, read_xlsx


def test_html_footnote_markers_are_dropped(tmp_path):
    page = tmp_path / "bag1.htm"
    page.write_bytes(
        b"<html><table>"
        b"<tr><th>Item</th><TH>2010-2011<br>Budget</TH></tr>"
        b"<tr><td>Recoveries of Loans<sup>1</sup></td><td align=right>62043<SUP>*</SUP></td></tr>"
        b"<tr><td> </td><td>&nbsp;</td></tr>"  # an empty row: left out
        b"<tr><td>Grants&nbsp;&amp;\n  loans\xa0</td><td><b>1,000</b></td></tr>"
        b"</table></html>")
    assert read_html(page) == [["Item", "2010-2011 Budget"], ["Recoveries of Loans", "62043"],
                               ["Grants & loans", "1,000"]]


class FakePage:
    """The part of a pdfplumber page drop_small_chars uses: filter() keeps the objects the test accepts."""

    def __init__(self, objects):
        self.objects = objects

    def filter(self, test):
        return FakePage([o for o in self.objects if test(o)])


def test_pdf_superscript_footnote_characters_are_dropped():
    objects = [
        {"object_type": "char", "text": "6", "size": 9.0},
        {"object_type": "char", "text": "1", "size": 6.0},  # a superscript footnote marker
        {"object_type": "char", "text": "2", "size": 7.0},  # at the cut-off: kept
        {"object_type": "char", "text": "?"},  # no size: kept
        {"object_type": "rect", "size": 1.0},  # not a character: kept
    ]
    kept = drop_small_chars(FakePage(objects), 7.0).objects
    assert [o.get("text") for o in kept] == ["6", "2", "?", None]


@pytest.mark.parametrize("token", ["62043", "1,23,456.78", "62043$", "140955*", "(4.3)", "-(0.2)", "(-)", "-",
                                   "...", "…", "-1732"])
def test_value_tokens_at_the_end_of_a_pdf_line(token):
    assert NUM_TOKEN.match(token)


@pytest.mark.parametrize("token", ["2010-11", "Deficit", "1a", "#", "1.2.3"])
def test_label_tokens_are_not_values(token):
    assert not NUM_TOKEN.match(token)


def test_xlsx_numbers_read_as_printed(tmp_path):
    path = tmp_path / "bag1.xlsx"
    book = openpyxl.Workbook()
    sheet = book.active
    sheet.append(["Revenue  Receipts\n", 540259.0, 1.5, None, 7])
    sheet.append([None, None])  # an empty row: left out
    sheet.append(["Fiscal Deficit", -381408.0, "(5.5)"])
    book.create_sheet("Notes").append(["only the first sheet is read"])
    book.save(path)
    assert read_xlsx(path) == [["Revenue Receipts", "540259", "1.5", "", "7"],
                               ["Fiscal Deficit", "-381408", "(5.5)", "", ""]]


def test_read_any_picks_the_reader_by_extension(tmp_path):
    page = tmp_path / "BAG1.HTM"
    page.write_bytes(b"<table><tr><td>Budget at a Glance</td></tr></table>")
    assert read_any(page) == [["Budget at a Glance"]]
    with pytest.raises(KeyError):
        read_any(tmp_path / "bag1.csv")

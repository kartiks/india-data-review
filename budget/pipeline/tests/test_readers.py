"""The steps the PDF line readers share (readers.py)."""

from budget_pipeline.readers import body_size, group_lines


def word(text, x0, bottom):
    return {"text": text, "x0": x0, "x1": x0 + 10, "bottom": bottom}


def test_group_lines_by_bottom_edge_within_tolerance():
    words = [word("62043", 200, 100.0), word("Revenue", 10, 101.2), word("$", 215, 97.8), word("Capital", 10, 112.0)]
    lines = group_lines(words, tol=2.5)
    assert [[w["text"] for w in line] for line in lines] == [["Revenue", "62043", "$"], ["Capital"]]
    # With a tighter tolerance the "$" printed 2.2 points higher is a line of its own.
    assert len(group_lines(words, tol=2.0)) == 3


def test_body_size_is_the_most_common_size():
    assert body_size([8.5, 8.5, 6.0, 10.0, 8.5], 10.0) == 8.5
    assert body_size([], 8.0) == 8.0

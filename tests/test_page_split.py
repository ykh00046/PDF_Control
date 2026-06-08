"""Tests for the page-merge-split feature.

Covers the pure grouping logic (app.page_split) plus the I/O-bound
DocumentSession.split_document / merge_pdfs methods.
"""
import fitz
import pytest

from app.model import DocumentSession
from app.page_split import SplitMode, compute_split_groups, parse_page_ranges


@pytest.fixture
def multi_page_pdf(tmp_path):
    """Create a 5-page PDF with identifiable text on each page."""
    pdf_path = tmp_path / "multi.pdf"
    doc = fitz.open()
    for i in range(5):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 72), f"PAGE {i + 1}", fontsize=24)
    doc.save(str(pdf_path))
    doc.close()
    return str(pdf_path)


def _make_pdf(path, n):
    doc = fitz.open()
    for i in range(n):
        page = doc.new_page(width=595, height=842)
        page.insert_text((72, 72), f"SRC {i + 1}", fontsize=24)
    doc.save(str(path))
    doc.close()
    return str(path)


# --------------------------------------------------------------------------
# parse_page_ranges
# --------------------------------------------------------------------------
class TestParsePageRanges:
    def test_mixed_ranges_and_singles(self):
        assert parse_page_ranges("1-3, 5, 7-9", 9) == [[0, 1, 2], [4], [6, 7, 8]]

    def test_whitespace_tolerant(self):
        assert parse_page_ranges("  2 - 3 ,  5 ", 5) == [[1, 2], [4]]

    def test_single_page(self):
        assert parse_page_ranges("3", 5) == [[2]]

    def test_overlap_allowed_and_ordered(self):
        assert parse_page_ranges("3-4, 1-2", 5) == [[2, 3], [0, 1]]

    @pytest.mark.parametrize("spec", ["", "   ", ",", "1,,2"])
    def test_empty_or_blank_groups_rejected(self, spec):
        with pytest.raises(ValueError):
            parse_page_ranges(spec, 5)

    def test_reversed_range_rejected(self):
        with pytest.raises(ValueError):
            parse_page_ranges("5-3", 9)

    def test_out_of_range_rejected(self):
        with pytest.raises(ValueError):
            parse_page_ranges("1-99", 9)

    def test_zero_rejected(self):
        with pytest.raises(ValueError):
            parse_page_ranges("0-2", 9)

    def test_non_integer_rejected(self):
        with pytest.raises(ValueError):
            parse_page_ranges("1-a", 9)


# --------------------------------------------------------------------------
# compute_split_groups
# --------------------------------------------------------------------------
class TestComputeSplitGroups:
    def test_single_mode(self):
        assert compute_split_groups(3, SplitMode.SINGLE) == [[0], [1], [2]]

    def test_every_n_even(self):
        assert compute_split_groups(4, SplitMode.EVERY_N, every_n=2) == [[0, 1], [2, 3]]

    def test_every_n_with_remainder(self):
        assert compute_split_groups(5, SplitMode.EVERY_N, every_n=2) == [
            [0, 1], [2, 3], [4]
        ]

    def test_every_n_requires_positive(self):
        with pytest.raises(ValueError):
            compute_split_groups(5, SplitMode.EVERY_N, every_n=0)

    def test_ranges_mode_delegates(self):
        assert compute_split_groups(
            9, SplitMode.RANGES, ranges_spec="1-3,5"
        ) == [[0, 1, 2], [4]]

    def test_ranges_requires_spec(self):
        with pytest.raises(ValueError):
            compute_split_groups(5, SplitMode.RANGES)

    def test_non_positive_page_count_rejected(self):
        with pytest.raises(ValueError):
            compute_split_groups(0, SplitMode.SINGLE)


# --------------------------------------------------------------------------
# DocumentSession.split_document
# --------------------------------------------------------------------------
class TestSplitDocument:
    def test_single_mode_writes_one_file_per_page(self, multi_page_pdf, tmp_path):
        session = DocumentSession(multi_page_pdf)
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        groups = compute_split_groups(5, SplitMode.SINGLE)
        written = session.split_document(str(out_dir), groups)
        assert len(written) == 5
        for path in written:
            d = fitz.open(path)
            assert d.page_count == 1
            d.close()
        # Source is untouched.
        assert session.doc.page_count == 5
        assert session.modified is False
        session.close()

    def test_every_n_page_composition(self, multi_page_pdf, tmp_path):
        session = DocumentSession(multi_page_pdf)
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        groups = compute_split_groups(5, SplitMode.EVERY_N, every_n=2)
        written = session.split_document(str(out_dir), groups)
        assert len(written) == 3  # ceil(5/2)
        counts = []
        for path in written:
            d = fitz.open(path)
            counts.append(d.page_count)
            d.close()
        assert counts == [2, 2, 1]
        session.close()

    def test_ranges_preserve_content(self, multi_page_pdf, tmp_path):
        session = DocumentSession(multi_page_pdf)
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        groups = compute_split_groups(5, SplitMode.RANGES, ranges_spec="1-2, 4")
        written = session.split_document(str(out_dir), groups)
        assert len(written) == 2
        first = fitz.open(written[0])
        assert first.page_count == 2
        assert "PAGE 1" in first[0].get_text()
        assert "PAGE 2" in first[1].get_text()
        first.close()
        second = fitz.open(written[1])
        assert second.page_count == 1
        assert "PAGE 4" in second[0].get_text()
        second.close()
        session.close()

    def test_custom_base_name(self, multi_page_pdf, tmp_path):
        session = DocumentSession(multi_page_pdf)
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        written = session.split_document(
            str(out_dir), [[0], [1]], base_name="chapter"
        )
        assert written[0].endswith("chapter_001.pdf")
        assert written[1].endswith("chapter_002.pdf")
        session.close()

    def test_empty_groups_rejected(self, multi_page_pdf, tmp_path):
        session = DocumentSession(multi_page_pdf)
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        with pytest.raises(ValueError):
            session.split_document(str(out_dir), [])
        with pytest.raises(ValueError):
            session.split_document(str(out_dir), [[]])
        session.close()

    def test_missing_output_dir_rejected(self, multi_page_pdf, tmp_path):
        session = DocumentSession(multi_page_pdf)
        with pytest.raises(ValueError):
            session.split_document(str(tmp_path / "nope"), [[0]])
        session.close()

    def test_out_of_range_index_rejected(self, multi_page_pdf, tmp_path):
        session = DocumentSession(multi_page_pdf)
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        with pytest.raises(IndexError):
            session.split_document(str(out_dir), [[99]])
        session.close()


# --------------------------------------------------------------------------
# DocumentSession.merge_pdfs (+ merge_pdf delegation)
# --------------------------------------------------------------------------
class TestMergePdfs:
    def test_merge_multiple_in_order(self, multi_page_pdf, tmp_path):
        session = DocumentSession(multi_page_pdf)  # 5 pages
        a = _make_pdf(tmp_path / "a.pdf", 2)
        b = _make_pdf(tmp_path / "b.pdf", 3)
        added = session.merge_pdfs([a, b])
        assert added == 5
        assert session.doc.page_count == 10
        # a's pages land right after the original 5, then b's.
        assert "SRC 1" in session.doc[5].get_text()
        assert "SRC 1" in session.doc[7].get_text()  # start of b
        session.close()

    def test_merge_after_index(self, multi_page_pdf, tmp_path):
        session = DocumentSession(multi_page_pdf)  # 5 pages
        a = _make_pdf(tmp_path / "a.pdf", 2)
        session.merge_pdfs([a], after_index=0)  # insert after page 1
        assert session.doc.page_count == 7
        assert "SRC 1" in session.doc[1].get_text()
        session.close()

    def test_empty_list_rejected(self, multi_page_pdf):
        session = DocumentSession(multi_page_pdf)
        with pytest.raises(ValueError):
            session.merge_pdfs([])
        session.close()

    def test_missing_file_rejected(self, multi_page_pdf, tmp_path):
        session = DocumentSession(multi_page_pdf)
        with pytest.raises(FileNotFoundError):
            session.merge_pdfs([str(tmp_path / "ghost.pdf")])
        session.close()

    def test_merge_pdf_single_delegates(self, multi_page_pdf, tmp_path):
        session = DocumentSession(multi_page_pdf)  # 5 pages
        a = _make_pdf(tmp_path / "a.pdf", 2)
        added = session.merge_pdf(a)
        assert added == 2
        assert session.doc.page_count == 7
        session.close()

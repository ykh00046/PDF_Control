import pytest
import fitz
from pathlib import Path
from app.model import DocumentSession, RemoveSectionAsImage

@pytest.fixture
def sample_pdf_with_sections(tmp_path):
    """3개의 명확한 섹션이 있는 PDF 생성"""
    pdf_path = tmp_path / "sections.pdf"

    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4

    # 상단 섹션 (0~200pt)
    page.insert_text((50, 50), "TOP SECTION", fontsize=20)
    page.insert_text((50, 100), "This is the top part of the document.", fontsize=12)

    # 중간 섹션 (300~500pt) - 이 부분을 제거할 예정
    page.insert_text((50, 350), "MIDDLE SECTION (TO BE REMOVED)", fontsize=20)
    page.insert_text((50, 400), "This middle part will be removed.", fontsize=12)

    # 하단 섹션 (600~800pt)
    page.insert_text((50, 650), "BOTTOM SECTION", fontsize=20)
    page.insert_text((50, 700), "This is the bottom part of the document.", fontsize=12)

    doc.save(str(pdf_path))
    doc.close()

    return pdf_path

def test_remove_middle_section(sample_pdf_with_sections, tmp_path):
    """중간 영역 제거 테스트"""
    output_path = tmp_path / "output_removed.pdf"
    session = None
    result_doc = None

    try:
        session = DocumentSession(str(sample_pdf_with_sections))
        page = session.doc[0]
        original_height = page.rect.height

        # 중간 영역 제거 (300~500pt, 높이 200pt)
        remove_rect = fitz.Rect(0, 300, 595, 500)
        op = RemoveSectionAsImage(0, remove_rect, dpi=150, format="jpeg")

        session.add_operation(op)
        session.save_document(str(output_path))

        # 검증
        result_doc = fitz.open(str(output_path))
        result_page = result_doc[0]

        # 페이지 높이가 200pt 줄어들었는지 확인
        expected_height = original_height - 200
        assert abs(result_page.rect.height - expected_height) < 5, \
            f"Expected height {expected_height}, got {result_page.rect.height}"

        # 텍스트 확인 (전체가 이미지화되어 get_text()는 빈 문자열)
        text = result_page.get_text()
        assert text == "", "Page should be converted to image (no extractable text)"

        # 이미지가 삽입되었는지 확인
        images = result_page.get_images()
        assert len(images) == 1, "Should have exactly one image"

        print(f"✓ Middle section removed: height {original_height:.1f}pt → {result_page.rect.height:.1f}pt")

    finally:
        if session:
            session.close()
        if result_doc:
            result_doc.close()

def test_remove_top_section(sample_pdf_with_sections, tmp_path):
    """상단 영역 제거 테스트 (하단만 남음)"""
    output_path = tmp_path / "output_top_removed.pdf"
    session = None
    result_doc = None

    try:
        session = DocumentSession(str(sample_pdf_with_sections))
        page = session.doc[0]
        original_height = page.rect.height

        # 상단 영역 제거 (0~400pt)
        remove_rect = fitz.Rect(0, 0, 595, 400)
        op = RemoveSectionAsImage(0, remove_rect, dpi=150, format="png")

        session.add_operation(op)
        session.save_document(str(output_path))

        # 검증
        result_doc = fitz.open(str(output_path))
        result_page = result_doc[0]

        # 페이지 높이 확인
        expected_height = original_height - 400
        assert abs(result_page.rect.height - expected_height) < 5

        # 이미지 존재 확인
        images = result_page.get_images()
        assert len(images) == 1

        print(f"✓ Top section removed: height {original_height:.1f}pt → {result_page.rect.height:.1f}pt")

    finally:
        if session:
            session.close()
        if result_doc:
            result_doc.close()

def test_remove_bottom_section(sample_pdf_with_sections, tmp_path):
    """하단 영역 제거 테스트 (상단만 남음)"""
    output_path = tmp_path / "output_bottom_removed.pdf"
    session = None
    result_doc = None

    try:
        session = DocumentSession(str(sample_pdf_with_sections))
        page = session.doc[0]
        original_height = page.rect.height

        # 하단 영역 제거 (550~끝)
        remove_rect = fitz.Rect(0, 550, 595, original_height)
        op = RemoveSectionAsImage(0, remove_rect, dpi=300, format="jpeg")

        session.add_operation(op)
        session.save_document(str(output_path))

        # 검증
        result_doc = fitz.open(str(output_path))
        result_page = result_doc[0]

        # 페이지 높이 확인
        removed_height = original_height - 550
        expected_height = 550
        assert abs(result_page.rect.height - expected_height) < 5

        # 이미지 존재 확인
        images = result_page.get_images()
        assert len(images) == 1

        print(f"✓ Bottom section removed: height {original_height:.1f}pt → {result_page.rect.height:.1f}pt")

    finally:
        if session:
            session.close()
        if result_doc:
            result_doc.close()

def test_remove_entire_page_fails(sample_pdf_with_sections, tmp_path):
    """전체 페이지 제거 시도는 실패해야 함"""
    output_path = tmp_path / "output_fail.pdf"
    session = None

    try:
        session = DocumentSession(str(sample_pdf_with_sections))
        page = session.doc[0]

        # 전체 페이지 제거 시도
        remove_rect = fitz.Rect(0, 0, 595, page.rect.height)
        op = RemoveSectionAsImage(0, remove_rect, dpi=150, format="jpeg")

        session.add_operation(op)

        # ValueError 발생 예상
        with pytest.raises(ValueError, match="result would be empty page"):
            session.save_document(str(output_path))

        print("✓ Empty page removal correctly rejected")

    finally:
        if session:
            session.close()

def test_jpeg_vs_png_format(sample_pdf_with_sections, tmp_path):
    """JPEG와 PNG 포맷 비교 테스트"""
    jpeg_path = tmp_path / "output_jpeg.pdf"
    png_path = tmp_path / "output_png.pdf"
    session_jpeg = None
    session_png = None

    try:
        # JPEG 버전
        session_jpeg = DocumentSession(str(sample_pdf_with_sections))
        remove_rect = fitz.Rect(0, 300, 595, 500)
        op_jpeg = RemoveSectionAsImage(0, remove_rect, dpi=150, format="jpeg")
        session_jpeg.add_operation(op_jpeg)
        session_jpeg.save_document(str(jpeg_path))

        # PNG 버전
        session_png = DocumentSession(str(sample_pdf_with_sections))
        op_png = RemoveSectionAsImage(0, remove_rect, dpi=150, format="png")
        session_png.add_operation(op_png)
        session_png.save_document(str(png_path))

        # 파일 크기 비교
        jpeg_size = jpeg_path.stat().st_size
        png_size = png_path.stat().st_size

        print(f"✓ JPEG size: {jpeg_size / 1024:.1f}KB, PNG size: {png_size / 1024:.1f}KB")

        # 일반적으로 JPEG가 더 작아야 함 (항상 보장되지는 않음)
        assert jpeg_size > 0 and png_size > 0, "Both files should exist"

    finally:
        if session_jpeg:
            session_jpeg.close()
        if session_png:
            session_png.close()

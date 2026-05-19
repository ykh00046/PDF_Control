
import fitz
import os
import sys

# 프로젝트 루트 경로 추가
sys.path.append(os.getcwd())

from app.model import _extract_text_metadata, RedactReplace

def test_style_extraction():
    print("--- 스타일 상속(Style Inheritance) 검증 시작 ---")
    
    # 1. 테스트용 PDF 생성
    doc = fitz.open()
    page = doc.new_page()
    
    # 빨간색 (1, 0, 0), 20pt, Helvetica-Bold 느낌의 텍스트 삽입
    # 참고: insert_text에서 color는 RGB 튜플 (0-1)
    text_rect = fitz.Rect(50, 50, 200, 80)
    page.insert_text((50, 70), "STYLE TEST", fontsize=20, color=(1, 0, 0))
    
    # 2. 메타데이터 추출 테스트
    print(f"1. [{text_rect}] 영역에서 스타일 추출 중...")
    meta = _extract_text_metadata(page, text_rect)
    
    print(f"   - 추출된 폰트 크기: {meta['fontsize']:.1f}pt (기대값: ~20.0pt)")
    print(f"   - 추출된 색상: {meta['color']} (기대값: (1.0, 0.0, 0.0))")
    
    # 검증
    assert 19.0 <= meta['fontsize'] <= 21.0, f"폰트 크기 오류: {meta['fontsize']}"
    assert meta['color'] == (1.0, 0.0, 0.0), f"색상 추출 오류: {meta['color']}"
    
    # 3. RedactReplace 오퍼레이션 생성 및 데이터 보존 확인
    print("2. RedactReplace 오퍼레이션 생성 및 직렬화 테스트...")
    op = RedactReplace(
        page_index=0, 
        rects=[text_rect], 
        new_text="REPLACED",
        fontsize=meta['fontsize'],
        color=meta['color'],
        font_flags=meta['font_flags']
    )
    
    op_dict = op.to_dict()
    print(f"   - 직렬화 데이터 색상: {op_dict['color']}")
    assert op_dict['color'] == [1.0, 0.0, 0.0], "오퍼레이션 색상 저장 오류"
    
    print("\n✅ 스타일 상속 기능 검증 성공!")
    doc.close()

if __name__ == "__main__":
    try:
        test_style_extraction()
    except Exception as e:
        print(f"\n❌ 검증 실패: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

import sys
from pathlib import Path

# 프로젝트 루트 경로 추가 (파일 위치 기준 — cwd 무관)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import fitz
from PySide6.QtWidgets import QApplication

# QApplication 인스턴스 생성 (UI 위젯 테스트용)
app = QApplication.instance() or QApplication(sys.argv)

from app.remove_section_dialog import RemoveSectionDialog


def test_precision_rect_passing():
    print("--- 3번 편집 정밀도 UI 강화 로직 검증 시작 ---")

    # 1. 가상 데이터 준비
    doc = fitz.open()
    page = doc.new_page()
    initial_rect = fitz.Rect(0, 100, 595, 200)  # 초기 드래그 영역

    # 2. 다이얼로그 생성 및 수치 변경 시뮬레이션
    print(f"1. 초기 영역 {initial_rect}으로 다이얼로그 생성...")
    dialog = RemoveSectionDialog(page, initial_rect)

    # Y0를 50.5pt로, Y1을 250.0pt로 정밀 조정 시뮬레이션
    print("2. 좌표 정밀 조정 시뮬레이션 (Y0: 50.5, Y1: 250.0)")
    dialog.y0_spin.setValue(50.5)
    dialog.y1_spin.setValue(250.0)

    # 3. 시그널을 통해 전달되는 데이터 검증
    print("3. 전달 데이터 검증 중...")
    captured_data = {}

    def on_confirmed(data):
        nonlocal captured_data
        captured_data = data

    dialog.remove_confirmed.connect(on_confirmed)
    dialog.apply_remove()  # 적용 버튼 클릭 시뮬레이션

    # 최종 rect 검증
    final_rect = captured_data.get("rect")
    print(f"   - 최종 전달 좌표: {final_rect}")

    assert final_rect.y0 == 50.5, f"Y0 좌표 불일치: {final_rect.y0}"
    assert final_rect.y1 == 250.0, f"Y1 좌표 불일치: {final_rect.y1}"
    assert captured_data["dpi"] == 300, "기본 DPI 오류"

    print("\n✅ 3번 편집 정밀도 UI 강화 로직 검증 성공!")
    doc.close()


if __name__ == "__main__":
    try:
        test_precision_rect_passing()
    except Exception as e:
        print(f"\n❌ 검증 실패: {e}")
        sys.exit(1)

# -*- coding: utf-8 -*-
"""run_classification_eval.py가 남긴 결과 JSON을 부서별 막대그래프로 시각화한다.

"1차_부서 정확도"/"1차_문의유형 정확도"처럼 회차를 구분해서 볼 수 있게, 파일명과
차트 제목에 회차 라벨(기본값 "1차")을 붙인다. rules.yaml 등을 고쳐서 다시 측정하면
--round 2차로 다시 실행해 같은 부서 축 위에서 비교할 수 있다.

실행:
    cd test
    ../.venv/Scripts/python.exe visualize_eval_results.py
    ../.venv/Scripts/python.exe visualize_eval_results.py --round 2차 --result results/classification_eval_<타임스탬프>.json
"""
import argparse
import json
from pathlib import Path

import matplotlib.pyplot as plt

RESULTS_DIR = Path(__file__).resolve().parent / "results"

# 윈도우 기본 한글 폰트. 다른 OS에서 돌릴 경우 폰트명만 바꾸면 된다(예: 맥 'AppleGothic').
plt.rcParams["font.family"] = "Malgun Gothic"
plt.rcParams["axes.unicode_minus"] = False

# dataviz 스킬 참조 팔레트에서 검증(validate_palette.js)까지 마친 2색 조합.
# 앱 기존 teal(#0E8C86)은 채도가 낮아 범주형 비교 차트엔 부적합(채도 하한 FAIL)해서 쓰지 않았다.
COLOR_DEPARTMENT = "#2a78d6"   # 부서 정확도
COLOR_INTENT = "#eb6834"      # 문의유형 정확도
INK_PRIMARY = "#0b0b0b"
INK_MUTED = "#898781"
GRIDLINE = "#e1e0d9"
BASELINE = "#c3c2b7"
SURFACE = "#fcfcfb"


def latest_result_file() -> Path:
    files = sorted(RESULTS_DIR.glob("classification_eval_*.json"))
    if not files:
        raise SystemExit(f"{RESULTS_DIR}에 결과 파일이 없습니다. run_classification_eval.py를 먼저 실행하세요.")
    return files[-1]


def load_summary(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["summary"]


def build_series(summary: dict):
    per_dept = summary["per_department"]
    # 부서명을 dept_correct 기준 내림차순으로 정렬 — 가장 취약한 부서가 오른쪽 끝에
    # 몰리게 해서 "어디부터 봐야 하는지"가 눈에 바로 들어오게 한다.
    departments = sorted(per_dept.keys(), key=lambda d: per_dept[d]["dept_correct"], reverse=True)

    labels = departments + ["전체"]
    dept_acc = [per_dept[d]["dept_correct"] / per_dept[d]["total"] * 100 for d in departments]
    dept_acc.append(summary["department_accuracy"] * 100)
    type_acc = [per_dept[d]["type_correct"] / per_dept[d]["total"] * 100 for d in departments]
    type_acc.append(summary["inquiry_type_accuracy"] * 100)
    return labels, dept_acc, type_acc


def draw_chart(labels, dept_acc, type_acc, round_label: str, out_path: Path):
    n = len(labels)
    x = range(n)
    bar_width = 0.36

    fig, ax = plt.subplots(figsize=(11, 6), dpi=150)
    fig.patch.set_facecolor(SURFACE)
    ax.set_facecolor(SURFACE)

    bars_dept = ax.bar(
        [i - bar_width / 2 for i in x], dept_acc, width=bar_width,
        color=COLOR_DEPARTMENT, label="부서 정확도", zorder=3,
    )
    bars_type = ax.bar(
        [i + bar_width / 2 for i in x], type_acc, width=bar_width,
        color=COLOR_INTENT, label="문의유형 정확도", zorder=3,
    )

    # "전체" 막대는 부서별 막대와 구분되게 살짝 연하게(요약값이지 개별 부서가 아님을 표시).
    bars_dept[-1].set_alpha(0.55)
    bars_type[-1].set_alpha(0.55)

    # 값 직접 라벨링 — 정적 이미지라 호버가 불가능해서, 막대마다 값을 바로 보여준다.
    for bars in (bars_dept, bars_type):
        for bar in bars:
            height = bar.get_height()
            ax.annotate(
                f"{height:.0f}%",
                xy=(bar.get_x() + bar.get_width() / 2, height),
                xytext=(0, 3), textcoords="offset points",
                ha="center", va="bottom", fontsize=8.5, color=INK_MUTED,
            )

    ax.set_ylim(0, 112)
    ax.set_ylabel("정확도 (%)", color=INK_MUTED, fontsize=10)
    ax.set_title(
        f"{round_label}_부서 정확도 · {round_label}_문의유형 정확도 (부서별)",
        color=INK_PRIMARY, fontsize=14, fontweight="bold", pad=16,
    )
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, color=INK_PRIMARY, fontsize=10)

    ax.yaxis.grid(True, color=GRIDLINE, linewidth=0.8, zorder=0)
    ax.set_axisbelow(True)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(BASELINE)
    ax.tick_params(axis="both", length=0, colors=INK_MUTED)

    legend = ax.legend(
        loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=2,
        frameon=False, fontsize=10, labelcolor=INK_PRIMARY,
    )

    fig.tight_layout()
    fig.savefig(out_path, facecolor=SURFACE, bbox_extra_artists=(legend,), bbox_inches="tight")
    print(f"차트 저장: {out_path}")


def print_table(labels, dept_acc, type_acc, round_label: str):
    # 접근성 대체 뷰(표) — 이미지 없이도 같은 정보를 확인할 수 있게 콘솔에 그대로 출력.
    print(f"\n=== {round_label} 정확도 표 ===")
    print(f"{'부서':10s} {'부서 정확도':>10s} {'문의유형 정확도':>14s}")
    for label, d, t in zip(labels, dept_acc, type_acc):
        print(f"{label:10s} {d:9.1f}% {t:13.1f}%")


def main():
    parser = argparse.ArgumentParser(description="분류 평가 결과를 부서별 막대그래프로 시각화")
    parser.add_argument("--result", type=str, default=None, help="결과 JSON 경로 (기본: 최신 파일)")
    parser.add_argument("--round", type=str, default="1차", help="회차 라벨 (기본: 1차)")
    args = parser.parse_args()

    result_path = Path(args.result) if args.result else latest_result_file()
    summary = load_summary(result_path)
    labels, dept_acc, type_acc = build_series(summary)

    print_table(labels, dept_acc, type_acc, args.round)

    out_path = RESULTS_DIR / f"{args.round}_accuracy_chart_{result_path.stem.split('_', 2)[-1]}.png"
    draw_chart(labels, dept_acc, type_acc, args.round, out_path)


if __name__ == "__main__":
    main()

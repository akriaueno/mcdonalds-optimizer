import streamlit as st
import sqlite3
import pandas as pd
from util.solver import get_data, solve
import subprocess
import html
import math

st.set_page_config(page_title="マクドナルド・オプティマイザー", layout="wide")


def build_nutrient_radar_svg(nutrient_rows):
    width = 760
    height = 560
    component_height = 640
    center_x = width / 2
    center_y = 300
    chart_radius = 180
    series_keys = [
        "lower_ratio",
        "recommended_ratio",
        "upper_ratio",
        "optimized_ratio",
    ]

    max_ratio = max(
        max(0.0, float(row[key]))
        for row in nutrient_rows
        for key in series_keys
    )
    max_ratio = max(1.2, math.ceil(max_ratio * 10) / 10)
    ring_values = sorted({0.5, 1.0, max_ratio})

    def point(index, ratio, radius=chart_radius):
        angle = -math.pi / 2 + (2 * math.pi * index / len(nutrient_rows))
        scaled_radius = radius * max(0.0, ratio) / max_ratio
        x = center_x + math.cos(angle) * scaled_radius
        y = center_y + math.sin(angle) * scaled_radius
        return x, y

    def points_for(ratios):
        return " ".join(
            f"{x:.1f},{y:.1f}"
            for x, y in [
                point(index, ratio) for index, ratio in enumerate(ratios)
            ]
        )

    grid_svg = []
    for value in ring_values:
        grid_svg.append(
            f'<polygon points="{points_for([value] * len(nutrient_rows))}" '
            'fill="none" stroke="#D1D5DB" stroke-width="1" />'
        )
        label_x, label_y = point(0, value)
        grid_svg.append(
            f'<text x="{label_x + 8:.1f}" y="{label_y + 4:.1f}" '
            'class="radar-grid-label">'
            f"{value * 100:.0f}%"
            "</text>"
        )

    axes_svg = []
    labels_svg = []
    for index, row in enumerate(nutrient_rows):
        axis_x, axis_y = point(index, max_ratio)
        axes_svg.append(
            f'<line x1="{center_x:.1f}" y1="{center_y:.1f}" '
            f'x2="{axis_x:.1f}" y2="{axis_y:.1f}" '
            'stroke="#E5E7EB" stroke-width="1" />'
        )

        angle = -math.pi / 2 + (2 * math.pi * index / len(nutrient_rows))
        label_radius = chart_radius + 54
        label_x = center_x + math.cos(angle) * label_radius
        label_y = center_y + math.sin(angle) * label_radius
        anchor = "middle"
        if label_x > center_x + 24:
            anchor = "start"
        elif label_x < center_x - 24:
            anchor = "end"

        labels_svg.append(
            f'<text x="{label_x:.1f}" y="{label_y:.1f}" '
            f'text-anchor="{anchor}" class="radar-label">'
            f"{html.escape(row['name'])}"
            "</text>"
        )

    lower_points = points_for([row["lower_ratio"] for row in nutrient_rows])
    recommended_points = points_for(
        [row["recommended_ratio"] for row in nutrient_rows]
    )
    upper_points = points_for([row["upper_ratio"] for row in nutrient_rows])
    optimized_points = points_for([row["optimized_ratio"] for row in nutrient_rows])

    return f"""
<style>
      html,
      body {{
        margin: 0;
        padding: 0;
        overflow: hidden;
      }}
      .nutrient-radar-wrap {{
        width: 100%;
        min-height: {component_height}px;
        overflow: visible;
        display: grid;
        justify-items: center;
        align-items: start;
        gap: 8px;
        font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      }}
      .radar-toggle-panel {{
        width: min(100%, {width}px);
        display: flex;
        flex-wrap: wrap;
        gap: 8px 12px;
        padding: 2px 4px 0;
        box-sizing: border-box;
      }}
      .series-toggle {{
        position: absolute;
        width: 1px;
        height: 1px;
        margin: -1px;
        opacity: 0;
        pointer-events: none;
      }}
      .legend-item {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        min-height: 30px;
        padding: 4px 8px;
        border: 1px solid #E5E7EB;
        border-radius: 6px;
        color: #374151;
        background: #FFFFFF;
        cursor: pointer;
        font-size: 13px;
        line-height: 1;
        user-select: none;
      }}
      .legend-item:hover {{
        border-color: #D1D5DB;
        background: #F9FAFB;
      }}
      .series-toggle:focus-visible + .legend-item {{
        outline: 2px solid #2563EB;
        outline-offset: 2px;
      }}
      .legend-swatch {{
        width: 14px;
        height: 14px;
        border: 2px solid currentColor;
        border-radius: 3px;
        box-sizing: border-box;
      }}
      .legend-swatch.is-line {{
        border-style: dashed;
        background: transparent;
      }}
      #series-lower:not(:checked) + .legend-item,
      #series-recommended:not(:checked) + .legend-item,
      #series-upper:not(:checked) + .legend-item,
      #series-optimized:not(:checked) + .legend-item {{
        opacity: 0.48;
      }}
      #series-lower:not(:checked) ~ .nutrient-radar-canvas .series-lower,
      #series-recommended:not(:checked) ~ .nutrient-radar-canvas .series-recommended,
      #series-upper:not(:checked) ~ .nutrient-radar-canvas .series-upper,
      #series-optimized:not(:checked) ~ .nutrient-radar-canvas .series-optimized {{
        opacity: 0;
        pointer-events: none;
      }}
      .nutrient-radar-canvas {{
        width: 100%;
        display: flex;
        justify-content: center;
        overflow: visible;
      }}
      .nutrient-radar-chart {{
        display: block;
        width: min(100%, {width}px);
        height: auto;
        overflow: visible;
      }}
      .radar-title {{
        fill: #111827;
        font-size: 18px;
        font-weight: 700;
      }}
      .radar-label {{
        fill: #374151;
        font-size: 13px;
        font-weight: 600;
      }}
      .radar-grid-label {{
        fill: #6B7280;
        font-size: 12px;
        font-variant-numeric: tabular-nums;
      }}
</style>
<div class="nutrient-radar-wrap">
  <div class="radar-toggle-panel" aria-label="栄養バランスの表示切替">
    <input id="series-lower" class="series-toggle" type="checkbox" checked />
    <label for="series-lower" class="legend-item">
      <span class="legend-swatch is-line" style="color: #2563EB;"></span>
      下限
    </label>
    <input id="series-recommended" class="series-toggle" type="checkbox" checked />
    <label for="series-recommended" class="legend-item">
      <span class="legend-swatch" style="color: #D97706; background: rgba(245, 158, 11, 0.16);"></span>
      推奨値
    </label>
    <input id="series-upper" class="series-toggle" type="checkbox" checked />
    <label for="series-upper" class="legend-item">
      <span class="legend-swatch is-line" style="color: #DC2626;"></span>
      上限
    </label>
    <input id="series-optimized" class="series-toggle" type="checkbox" checked />
    <label for="series-optimized" class="legend-item">
      <span class="legend-swatch" style="color: #0F766E; background: rgba(15, 118, 110, 0.22);"></span>
      最適化結果
    </label>
    <div class="nutrient-radar-canvas">
      <svg class="nutrient-radar-chart" viewBox="0 0 {width} {height}" role="img" aria-label="下限、推奨値、上限、最適化結果の栄養バランス">
        <title>栄養バランス</title>
        <desc>凡例をクリックすると、下限、推奨値、上限、最適化結果の表示を切り替えられます。</desc>
        <text x="24" y="34" class="radar-title">栄養バランス</text>
        {"".join(grid_svg)}
        {"".join(axes_svg)}
        <polygon class="radar-series series-lower" points="{lower_points}" fill="none" stroke="#2563EB" stroke-width="2.5" stroke-dasharray="7 5" />
        <polygon class="radar-series series-recommended" points="{recommended_points}" fill="#F59E0B" fill-opacity="0.12" stroke="#D97706" stroke-width="2.5" />
        <polygon class="radar-series series-upper" points="{upper_points}" fill="none" stroke="#DC2626" stroke-width="2.5" stroke-dasharray="7 5" />
        <polygon class="radar-series series-optimized" points="{optimized_points}" fill="#0F766E" fill-opacity="0.24" stroke="#0F766E" stroke-width="3" />
        {"".join(labels_svg)}
      </svg>
    </div>
  </div>
</div>
"""


@st.cache_resource
def init_data():
    # ../scripts/init.sh スクリプトを実行してデータをダウンロード
    result = subprocess.run(["./scripts/init.sh"], capture_output=True, text=True)

    if result.returncode != 0:
        st.error("スクリプトの実行に失敗しました。エラーメッセージ: " + result.stderr)
        return False

    return True


if __name__ == "__main__":
    if init_data():
        st.success("データの初期化が完了しました。")

# DB接続
con = sqlite3.connect("./data/mcdonalds.sqlite")
menus, nutrients, nutrient_types = get_data(con)

st.title("マクドナルド・オプティマイザー")
st.text("栄養素の目標値を満たしつつ、最小の金額のメニューを提案します。")

st.sidebar.header("栄養素の制約を設定")

exclude_zero_price = st.sidebar.checkbox("0円メニューを禁止", value=True)
max_items_per_menu = st.sidebar.number_input(
    "同じメニューの最大選択個数", min_value=1, value=3, step=1
)

num_of_meals = st.sidebar.number_input("何食分", min_value=1, value=1, step=1)

# 栄養素の目標値
nutrient_targets = [
    {"id": 1, "name": "エネルギー", "target": 2200 / 3 * num_of_meals},
    {"id": 3, "name": "たんぱく質", "target": 81 / 3 * num_of_meals},
    {"id": 4, "name": "脂質", "target": 62 / 3 * num_of_meals},
    {"id": 5, "name": "炭水化物", "target": 320 / 3 * num_of_meals},
    {"id": 8, "name": "カルシウム", "target": 680 / 3 * num_of_meals},
    {"id": 10, "name": "鉄分", "target": 6.8 / 3 * num_of_meals},
    {"id": 11, "name": "ビタミンA", "target": 770 / 3 * num_of_meals},
    {"id": 12, "name": "ビタミンB1", "target": 1.2 / 3 * num_of_meals},
    {"id": 13, "name": "ビタミンB2", "target": 1.4 / 3 * num_of_meals},
    {"id": 15, "name": "ビタミンC", "target": 100 / 3 * num_of_meals},
    {"id": 17, "name": "食物繊維", "target": 19 / 3 * num_of_meals},
    {"id": 18, "name": "食塩相当量", "target": 7 / 3 * num_of_meals},
]

constraint_rows = []
for nt in nutrient_targets:
    target = float(nt["target"])
    if target < 10:
        step = 0.1
    elif target < 100:
        step = 1.0
    else:
        step = 10.0

    constraint_rows.append(
        {
            "id": nt["id"],
            "name": nt["name"],
            "unit": nutrient_types[nt["id"]]["unit"],
            "default_lb": round(target * 0.8, 1),
            "default_ub": round(target * 1.2, 1),
            "step": step,
        }
    )

if st.sidebar.button("栄養素の制約をリセット", width="stretch"):
    for row in constraint_rows:
        st.session_state[f"constraint_lb_{num_of_meals}_{row['id']}"] = row[
            "default_lb"
        ]
        st.session_state[f"constraint_ub_{num_of_meals}_{row['id']}"] = row[
            "default_ub"
        ]
    st.rerun()

st.subheader("栄養素の制約")

header_cols = st.columns([2.4, 1.3, 1.3])
header_cols[0].markdown("**栄養素**")
header_cols[1].markdown("**下限**")
header_cols[2].markdown("**上限**")

constraint_error_names = []
nutrient_limits = {}

for row in constraint_rows:
    lb_key = f"constraint_lb_{num_of_meals}_{row['id']}"
    ub_key = f"constraint_ub_{num_of_meals}_{row['id']}"
    st.session_state.setdefault(lb_key, row["default_lb"])
    st.session_state.setdefault(ub_key, row["default_ub"])

    cols = st.columns([2.4, 1.3, 1.3])
    cols[0].write(f"{row['name']} ({row['unit']})")
    lb = cols[1].number_input(
        f"{row['name']}の下限",
        min_value=0.0,
        step=row["step"],
        format="%.1f",
        key=lb_key,
        label_visibility="collapsed",
    )
    ub = cols[2].number_input(
        f"{row['name']}の上限",
        min_value=0.0,
        step=row["step"],
        format="%.1f",
        key=ub_key,
        label_visibility="collapsed",
    )

    if lb > ub:
        constraint_error_names.append(row["name"])

    nutrient_limits[row["id"]] = {"lb": lb, "ub": ub}

has_constraint_error = len(constraint_error_names) > 0

if has_constraint_error:
    st.error("下限が上限を超えています: " + "、".join(constraint_error_names))


if st.button("最適化", disabled=has_constraint_error):
    with st.spinner("計算中"):
        result = solve(
            menus,
            nutrients,
            nutrient_limits,
            nutrient_types,
            exclude_zero_price=exclude_zero_price,
            max_items_per_menu=max_items_per_menu,
        )

    if result is not None:
        rows = []
        total_price = 0
        for menu_id, num in result.items():
            menu_name = menus[menu_id]["name"]
            menu_price = menus[menu_id]["price"]
            item_total_price = menu_price * num
            total_price += item_total_price
            rows.append(
                [
                    menu_name,
                    str(round(num)),
                    f"{menu_price}円",
                    f"{round(item_total_price)}円",
                ]
            )
        rows.append(["合計", "", "", f"{round(total_price)}円"])

        df = pd.DataFrame(rows, columns=["メニュー", "個数", "単価", "合計"])
        st.table(df)

        total_nutrients = {nt_id: 0 for nt_id in nutrient_types}
        for menu_id, num in result.items():
            for nt_id in nutrients[menu_id]:
                total_nutrients[nt_id] += nutrients[menu_id][nt_id] * num

        comparison_rows = []
        chart_rows = []
        for nt in nutrient_targets:
            nt_id = nt["id"]
            recommended = float(nt["target"])
            optimized = total_nutrients[nt_id]
            nutrient_name = nutrient_types[nt_id]["name"]
            unit = nutrient_types[nt_id]["unit"]
            ratio = optimized / recommended if recommended > 0 else 0
            lower_ratio = (
                nutrient_limits[nt_id]["lb"] / recommended if recommended > 0 else 0
            )
            upper_ratio = (
                nutrient_limits[nt_id]["ub"] / recommended if recommended > 0 else 0
            )

            chart_rows.append(
                {
                    "name": nutrient_name,
                    "lower_ratio": lower_ratio,
                    "recommended_ratio": 1.0,
                    "upper_ratio": upper_ratio,
                    "optimized_ratio": ratio,
                }
            )
            comparison_rows.append(
                [
                    nutrient_name,
                    f"{recommended:.1f} {unit}",
                    f"{optimized:.1f} {unit}",
                    f"{ratio * 100:.0f}%",
                ]
            )

        st.subheader("推奨値との比較")
        st.iframe(build_nutrient_radar_svg(chart_rows), height=700)

        comparison_df = pd.DataFrame(
            comparison_rows,
            columns=["栄養素", "推奨値", "最適化結果", "達成率"],
        )
        st.table(comparison_df)
    else:
        st.write("解が見つかりませんでした。")

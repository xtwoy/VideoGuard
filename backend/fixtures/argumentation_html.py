"""Self-contained HTML view of PEAD's argumentation graphs.

    python -m fixtures.argumentation_html              # write reports/pead-argumentation.html
    python -m fixtures.argumentation_html --check      # verify it matches the models

The page is generated from the same scenarios as ``fixtures.argumentation_report``,
so the HTML and the markdown report can never disagree. It is a single file with
inline CSS and inline SVG: no scripts, no fonts, no network, so it can be opened
from disk or shown offline during a demo.

Nothing here is measured on real video. The page shows which arguments exist,
which attacks point where, and which grounded label each argument receives.
"""
from __future__ import annotations

import argparse
from html import escape
import math
from pathlib import Path

from fixtures.argumentation_report import build

REPORT = Path(__file__).resolve().parents[1] / "reports" / "pead-argumentation.html"

LABEL_STYLE = {
    "IN": ("#ecfdf3", "#087443", "被接受"),
    "OUT": ("#fef3f2", "#b42318", "被击倒"),
    "UNDECIDED": ("#fffaeb", "#b54708", "未决"),
}
POLARITY_STYLE = {"SUPPORT": "#237c6c", "COUNTER": "#b54708", "UNCERTAINTY": "#667085"}


def h(value: object) -> str:
    return escape(str("" if value is None else value), quote=True)


def _graph_svg(scenario: dict) -> str:
    """Inline SVG: one column per argument, arrows for attacks."""
    arguments = scenario["arguments"]
    if not arguments:
        return ""
    width, height = 880, 310
    left, right, top = 150, 150, 80
    span = max(1, len(arguments) - 1)
    step = (width - left - right) / span if len(arguments) > 1 else 0
    position = {
        argument["id"]: (left + index * step, top + (index % 2) * 110)
        for index, argument in enumerate(arguments)
    }
    short = {argument["id"]: argument["kind"] for argument in arguments}
    parts = [f'<svg viewBox="0 0 {width} {height}" role="img" '
             f'aria-label="论证攻击关系图" class="graph">',
             '<defs><marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" '
             'markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
             '<path d="M 0 0 L 10 5 L 0 10 z" fill="#98a2b3"/></marker></defs>']
    for attack in scenario["attacks"]:
        source, target = attack["source"], attack["target"]
        if source not in position or target not in position:
            continue
        (x1, y1), (x2, y2) = position[source], position[target]
        # Reverse edges bend to opposite sides. Stop at the circle boundary:
        # arrows aimed at the centre would be hidden by the subsequently drawn node.
        dx, dy = x2 - x1, y2 - y1
        distance = math.hypot(dx, dy)
        mid_x = (x1 + x2) / 2 - dy / distance * 48
        mid_y = (y1 + y2) / 2 + dx / distance * 48
        start_length = math.hypot(mid_x - x1, mid_y - y1)
        end_length = math.hypot(mid_x - x2, mid_y - y2)
        start_x, start_y = x1 + (mid_x - x1) / start_length * 49, y1 + (mid_y - y1) / start_length * 49
        end_x, end_y = x2 + (mid_x - x2) / end_length * 49, y2 + (mid_y - y2) / end_length * 49
        parts.append(
            f'<path d="M {start_x:.0f} {start_y:.0f} Q {mid_x:.0f} {mid_y:.0f} {end_x:.0f} {end_y:.0f}" '
            f'fill="none" stroke="#667085" stroke-width="2" marker-end="url(#arrow)"/>')
    for argument in arguments:
        x, y = position[argument["id"]]
        fill, ink, _ = LABEL_STYLE.get(argument["label"], ("#f2f4f7", "#344054", ""))
        parts.append(
            f'<g><circle cx="{x:.0f}" cy="{y:.0f}" r="46" fill="{fill}" '
            f'stroke="{ink}" stroke-width="2"/>'
            f'<text x="{x:.0f}" y="{y - 6:.0f}" text-anchor="middle" font-size="13" '
            f'font-weight="700" fill="{ink}">{h(argument["label"])}</text>'
            f'<text x="{x:.0f}" y="{y + 12:.0f}" text-anchor="middle" font-size="10" '
            f'fill="#475467">{h(short[argument["id"]])}</text></g>')
        parts.append(
            f'<text x="{x:.0f}" y="{y + 68:.0f}" text-anchor="middle" font-size="10" '
            f'fill="{POLARITY_STYLE.get(argument["polarity"], "#667085")}">'
            f'{h(argument["polarity"])}</text>')
    parts.append("</svg>")
    return "".join(parts)


def _argument_table(scenario: dict) -> str:
    rows = "".join(
        f"<tr><td><code>{h(argument['id'])}</code></td>"
        f"<td>{h(argument['polarity'])}</td><td>{h(argument['kind'])}</td>"
        f"<td class=\"label {h(argument['label'])}\">{h(argument['label'])}</td>"
        f"<td>{h(', '.join(argument['premise_ids']))}</td></tr>"
        for argument in scenario["arguments"])
    return ("<table><thead><tr><th>论证</th><th>极性</th><th>类型</th>"
            f"<th>grounded 标签</th><th>前提</th></tr></thead><tbody>{rows}</tbody></table>")


def _attack_list(scenario: dict) -> str:
    if not scenario["attacks"]:
        return '<p class="muted">无攻击关系：该事件内没有相互冲突的论证。</p>'
    items = "".join(
        f"<li><code>{h(attack['source'])}</code> → <code>{h(attack['target'])}</code></li>"
        for attack in scenario["attacks"])
    return f"<ul class=\"attacks\">{items}</ul>"


def render(report: dict) -> str:
    first = report["scenarios"][0]
    solver = first["solver"]
    ruleset = first["ruleset"]
    sections = []
    for index, scenario in enumerate(report["scenarios"], 1):
        finding = scenario["finding"]
        cycles = ("；存在循环 " + "、".join(" ↔ ".join(cycle) for cycle in scenario["cycles"])
                  if scenario["cycles"] else "")
        sections.append(f"""
    <section class="scenario">
      <h2>{index}. {h(scenario['name'])}</h2>
      <p class="why">{h(scenario['why'])}</p>
      <p class="muted">线索：{h('、'.join(scenario['cue_ids']))}</p>
      {_graph_svg(scenario)}
      {_argument_table(scenario)}
      <h3>攻击关系</h3>
      {_attack_list(scenario)}
      <p class="verdict">裁决：<b>{h(finding['judgement'])} / {h(finding['disposition'])}</b>
        <code>{h(finding['reason_code'])}</code></p>
      <p class="muted">标签统计 {h(scenario['labels'])}{h(cycles)}</p>
    </section>""")

    problems = ("<p class='ok'>检查通过：每个场景的标签与攻击符合预期。</p>"
                if not report["problems"]
                else "<ul class='bad'>" + "".join(f"<li>{h(p)}</li>"
                                                  for p in report["problems"]) + "</ul>")
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
<title>PEAD 论证攻防报告</title>
<style>
:root{{--ink:#1f3936;--teal:#237c6c;--line:#dbe2dc;--muted:#698078}}
*{{box-sizing:border-box}}
body{{margin:0;background:#f7f5ef;color:var(--ink);
  font:15px/1.65 "Microsoft YaHei","Noto Sans SC",system-ui,sans-serif}}
main{{max-width:980px;margin:auto;padding:46px 28px 72px}}
.eyebrow{{font-size:11px;color:var(--teal);font-weight:800;letter-spacing:.16em}}
h1{{font-size:30px;line-height:1.2;margin:8px 0}}
h2{{font-size:21px;margin:40px 0 10px}}h3{{font-size:15px;margin:20px 0 6px}}
.meta,.muted,.why{{color:var(--muted);font-size:13px}}
.notice{{background:#fff4e3;border-left:3px solid #d59b45;padding:14px 16px;margin:22px 0;
  font-size:13px}}
.scenario{{border:1px solid var(--line);border-radius:10px;background:#fff;
  padding:20px 22px;margin:18px 0;break-inside:avoid}}
.graph{{width:100%;height:auto;background:#fcfcfd;border-radius:8px;margin:10px 0}}
table{{border-collapse:collapse;width:100%;font-size:13px}}
th,td{{border-bottom:1px solid var(--line);padding:7px 9px;text-align:left;
  vertical-align:top;overflow-wrap:anywhere}}
th{{background:#f8faf9;font-size:12px;color:var(--muted)}}
code{{font-size:12px;background:#f2f4f7;border-radius:4px;padding:1px 5px;
  overflow-wrap:anywhere}}
.label{{font-weight:700}}.label.IN{{color:#087443}}.label.OUT{{color:#b42318}}
.attacks{{padding-left:20px;font-size:13px}}
.verdict{{margin-top:14px;font-size:14px}}
.ok{{color:#087443}}.bad{{color:#b42318}}
footer{{border-top:1px solid var(--line);margin-top:36px;padding-top:14px;
  color:var(--muted);font-size:12px}}
</style></head><body><main>
<div class="eyebrow">VIDEOGUARD-E / PEAD ARGUMENTATION</div>
<h1>PEAD 论证攻防报告</h1>
<p class="meta">求解器 {h(solver['name'])} {h(solver['version'])}
（{h(solver['distribution'])}） + {h(solver['graph_library'])} {h(solver['graph_version'])}
· 语义 <code>{h(first['semantics'])}</code> · fallback={h(solver['fallback'])}</p>
<p class="meta">规则集 <code>{h(ruleset['id'])}</code> v{h(ruleset['version'])}
· 指纹 <code>{h(ruleset['sha256'][:16])}…</code></p>
<div class="notice"><b>适用范围：</b>上游观察为 fixture 合成数据；证据图构造、规则集与
PyArg 求解为真实代码。本页展示<b>决策机制</b>——哪些论证存在、谁攻击谁、各自得到什么
grounded 标签——<b>不度量真实视频上的准确率</b>。</div>
{"".join(sections)}
<h2>检查结果</h2>{problems}
<footer>由 <code>python -m fixtures.argumentation_html</code> 生成，请勿手工编辑。
<p>grounded 标签由完整攻击与防御关系决定，不能只看环的奇偶。
孤立的相互攻击也可能保持 UNDECIDED；本页首个场景由外部的 RELATION_MISSING 论证打破循环，
因此得到 IN / OUT。此处四个场景不覆盖所有可能的论证图。</p></footer>
</main></body></html>"""


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true",
                        help="verify the checked-in page matches the current models")
    args = parser.parse_args()

    report = build()
    html = render(report)
    if args.check:
        if not REPORT.exists() or REPORT.read_text(encoding="utf-8") != html:
            print("reports/pead-argumentation.html 与当前模型不一致")
            print("run: python -m fixtures.argumentation_html")
            return 1
        print("argumentation html is up to date")
        return 0

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(html, encoding="utf-8")
    print(f"已写入 {REPORT}")
    if report["problems"]:
        for problem in report["problems"]:
            print(f"  - {problem}")
        return 1
    print("检查通过：每个场景的标签与攻击符合预期。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

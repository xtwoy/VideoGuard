"""Data-derived, offline argumentation view. Use --check to verify artifacts.

The #figure view focuses engineering scenario 2 for document captures. HTML,
inline SVG and downloadable JSON use the same actual solver output. The upstream
observations and relation replies are synthetic, not real-video measurements.
"""
from __future__ import annotations

import argparse
import hashlib
from html import escape
import json
import math
from pathlib import Path

from fixtures.argumentation_report import build
from fixtures.argumentation_style import CSS

REPORT = Path(__file__).resolve().parents[1] / "reports" / "pead-argumentation.html"
REPORT_DATA = REPORT.with_suffix(".json")
FEATURED_SCENARIO = 1
LABEL_STYLE = {
    "IN": ("#edf7f2", "#23775d", "被接受"),
    "OUT": ("#fff2ef", "#b34d45", "被击倒"),
    "UNDECIDED": ("#fff7e8", "#916321", "未决"),
}
KIND_LABELS = {
    "LOCAL_PROMOTION": "本地鼓励线索", "MODEL_PROMOTION": "模型支持候选",
    "COUNTER_CONTEXT": "反向语境约束", "RELATION_MISSING": "关系核验缺失",
    "REFERENT_CONFLICT": "事件指代冲突", "MODEL_COUNTER": "模型反向候选",
    "COUNTER_REFERENT_CONFLICT": "反向指代冲突",
}
POLARITY_LABELS = {"SUPPORT": "支持", "COUNTER": "反向", "UNCERTAINTY": "不确定性"}
JUDGEMENT_LABELS = {
    "SUPPORTED": "支持成立", "NOT_SUPPORTED": "未获支持", "CONFLICTED": "语境冲突",
    "INSUFFICIENT": "信息不足", "UNAVAILABLE": "不可判断",
}
DISPOSITION_LABELS = {"FLAG": "标注关注", "REVIEW": "人工复核", "NONE": "无处置项"}


def h(value: object) -> str:
    return escape(str("" if value is None else value), quote=True)


def report_json(report: dict) -> bytes:
    """Stable bytes for both the downloadable data and its fingerprint."""
    return (json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf8")


def _graph_svg(scenario: dict, *, key: str = "graph") -> str:
    """One box per computed argument and one arrow per actual attack edge."""
    arguments = scenario["arguments"]
    if not arguments:
        return '<p class="muted">当前输入没有生成论证。</p>'
    width, box_width, box_height = 1080, 372, 178
    count = len(arguments)
    if count == 1:
        positions = [(354, 74)]
    elif count == 2:
        positions = [(44, 74), (664, 74)]
    elif count == 3:
        positions = [(44, 74), (354, 382), (664, 74)]
    else:
        positions = [(44 + (index % 2) * 620, 54 + (index // 2) * 260)
                     for index in range(count)]
    height = max(y for _, y in positions) + box_height + 66
    by_id = {argument["id"]: (x, y)
             for argument, (x, y) in zip(arguments, positions)}
    labels = {argument["id"]: argument["label"] for argument in arguments}
    edges = {(edge["source"], edge["target"]) for edge in scenario["attacks"]}
    parts = [
        f'<svg viewBox="0 0 {width} {height}" role="img" aria-labelledby="{key}-title {key}-desc" class="graph">',
        f'<title id="{key}-title">论证、攻击关系与 grounded 标签</title>',
        f'<desc id="{key}-desc">{h(scenario["name"])}。矩形为程序生成的论证，箭头从攻击方指向被攻击方。'
        f'共 {count} 个论证，{len(scenario["attacks"])} 条攻击边。</desc>',
        f'<defs><marker id="{key}-arrow" viewBox="0 0 10 10" refX="9" refY="5" '
        'markerWidth="8" markerHeight="8" orient="auto"><path d="M 0 0 L 10 5 L 0 10 z" fill="#5b7fb4"/></marker></defs>',
    ]
    for edge in scenario["attacks"]:
        source, target = edge["source"], edge["target"]
        x1, y1 = by_id[source]
        x2, y2 = by_id[target]
        cx1, cy1 = x1 + box_width / 2, y1 + box_height / 2
        cx2, cy2 = x2 + box_width / 2, y2 + box_height / 2
        dx, dy = cx2 - cx1, cy2 - cy1
        if (target, source) in edges and y1 == y2:
            # Reciprocal edges use different lanes instead of overlapping.
            lane = y1 - 34 if dx > 0 else y1 + box_height + 39
            start_y = y1 if dx > 0 else y1 + box_height
            end_y = y2 if dx > 0 else y2 + box_height
            path = f"M {cx1:.1f} {start_y:.1f} C {cx1:.1f} {lane:.1f}, {cx2:.1f} {lane:.1f}, {cx2:.1f} {end_y:.1f}"
            label_x, label_y = (cx1 + cx2) / 2, lane + (1 if dx > 0 else 8)
        else:
            # Intersect the centre-to-centre line with both box borders.
            scale = 1 / max(abs(dx) / (box_width / 2), abs(dy) / (box_height / 2))
            sx, sy = cx1 + dx * scale, cy1 + dy * scale
            ex, ey = cx2 - dx * scale, cy2 - dy * scale
            length = math.hypot(dx, dy)
            ex, ey = ex - dx / length * 6, ey - dy / length * 6
            path = f"M {sx:.1f} {sy:.1f} L {ex:.1f} {ey:.1f}"
            label_x, label_y = (sx + ex) / 2, (sy + ey) / 2 - 20
        edge_label = "攻击并击倒" if labels[source] == "IN" and labels[target] == "OUT" else "攻击"
        parts.append(
            f'<path class="attack-link" data-source="{h(source)}" data-target="{h(target)}" '
            f'd="{path}" fill="none" stroke="#5b7fb4" stroke-width="2.4" marker-end="url(#{key}-arrow)"/>'
            f'<text x="{label_x:.1f}" y="{label_y:.1f}" text-anchor="middle" class="edge-label">{edge_label}</text>')
    for argument, (x, y) in zip(arguments, positions):
        fill, ink, label = LABEL_STYLE.get(argument["label"], ("#f4f7fc", "#526983", "未知"))
        kind = argument["kind"]
        origin = "预设关系回答" if argument.get("origin") == "MODEL" else "结构规则"
        premises = "、".join(argument["premise_ids"]) or "未提供"
        parts.append(
            f'<g class="argument-node" data-argument-id="{h(argument["id"])}" data-label="{h(argument["label"])}">'
            f'<title>{h(argument["id"])}：{h(argument["label"])}</title>'
            f'<rect x="{x}" y="{y}" width="{box_width}" height="{box_height}" rx="13" fill="white" stroke="#cfdeef" stroke-width="1.5"/>'
            f'<rect x="{x + 1}" y="{y + 20}" width="4" height="38" rx="2" fill="{ink}"/>'
            f'<text x="{x + 25}" y="{y + 40}" class="node-title">{h(KIND_LABELS.get(kind, kind))}</text>'
            f'<rect x="{x + box_width - 81}" y="{y + 19}" width="59" height="28" rx="6" fill="{fill}"/>'
            f'<text x="{x + box_width - 51}" y="{y + 38}" text-anchor="middle" font-size="14" font-weight="700" fill="{ink}">{h(argument["label"])}</text>'
            f'<text x="{x + 25}" y="{y + 69}" class="node-kind">{h(kind)}</text>'
            f'<path d="M {x + 25} {y + 88} H {x + box_width - 25}" stroke="#e4ecf7"/>'
            f'<text x="{x + 25}" y="{y + 115}" class="node-premise">前提 {h(premises)}</text>'
            f'<text x="{x + 25}" y="{y + 146}" class="node-origin">{origin} · {h(label)}</text></g>')
    parts.append("</svg>")
    return '<div class="graph-scroll">' + "".join(parts) + "</div>"


def _argument_table(scenario: dict) -> str:
    rows = "".join(
        f'<tr><td><code>{h(argument["id"])}</code></td>'
        f'<td>{h(POLARITY_LABELS.get(argument["polarity"], argument["polarity"]))}</td>'
        f'<td><code>{h(argument["kind"])}</code></td>'
        f'<td class="label {h(argument["label"])}">{h(argument["label"])}</td>'
        f'<td>{h("、".join(argument["premise_ids"]))}</td></tr>'
        for argument in scenario["arguments"])
    return '<div class="table-scroll"><table><thead><tr><th>原始论证编号</th><th>极性</th><th>类型</th><th>标签</th><th>前提</th></tr></thead><tbody>' + rows + '</tbody></table></div>'


def _attack_list(scenario: dict) -> str:
    if not scenario["attacks"]:
        return '<p class="muted">无攻击关系：该事件内没有相互冲突的论证。</p>'
    items = "".join(
        f'<li><code>{h(edge["source"])}</code><span>攻击</span><code>{h(edge["target"])}</code></li>'
        for edge in scenario["attacks"])
    return f'<ul class="attacks">{items}</ul>'


def _scenario(scenario: dict, index: int, *, featured: bool = False) -> str:
    finding = scenario["finding"]
    judgement, disposition = finding["judgement"], finding["disposition"]
    traces = finding.get("event_decisions") or []
    selected_rule = (traces[0].get("decision_trace") or {}).get("selected_rule_id", "未提供") if traces else "未提供"
    counts = "".join(f'<span class="label {label}"><i></i>{label} {scenario["labels"].get(label, 0)}</span>'
                     for label in LABEL_STYLE)
    legend = '<div class="graph-key"><span>箭头从攻击方指向被攻击方</span>' + counts + '</div>'
    cycles = "；存在循环 " + "、".join(" ↔ ".join(cycle) for cycle in scenario["cycles"]) if scenario["cycles"] else "；无攻击环"
    details = f'''<details class="raw-record"><summary>核对原始论证与攻击记录<span>{len(scenario['arguments'])} 个论证 / {len(scenario['attacks'])} 条攻击</span></summary>
    {_argument_table(scenario)}<h4>攻击关系</h4>{_attack_list(scenario)}<p class="muted">标签统计 {h(scenario['labels'])}{h(cycles)}</p></details>'''
    cue_tags = ''.join(f'<b>{h(cue)}</b>' for cue in scenario['cue_ids'])
    body = f'''<header class="case-heading"><div><span class="case-source">工程场景 {index + 1:02d} · 冻结合成输入</span>
    <h2>{h(scenario['name'])}</h2></div><span class="case-state">{h(JUDGEMENT_LABELS.get(judgement, judgement))}</span></header>
    <p class="why">{h(scenario['why'])}</p><div class="cue-line"><span>引用线索</span>{cue_tags}<span>关系回答不作为新增观察证据</span></div>
    {_graph_svg(scenario, key=f'case-{index + 1}')}{legend}
    <div class="decision"><div><span>程序裁决</span><strong>{h(DISPOSITION_LABELS.get(disposition, disposition))}</strong><code>{h(judgement)} / {h(disposition)}</code></div>
    <dl><div><dt>触发规则</dt><dd>{h(selected_rule)}</dd></div><div><dt>原因代码</dt><dd>{h(finding['reason_code'])}</dd></div></dl></div>
    {details}'''
    if featured:
        return f'<section class="scenario featured" id="case-{index + 1}">{body}</section>'
    return f'<details class="scenario secondary-case" id="case-{index + 1}"><summary>{h(scenario["name"])}<span>{h(judgement)} / {h(disposition)}</span></summary><div>{body}</div></details>'


def render(report: dict) -> str:
    featured = report["scenarios"][FEATURED_SCENARIO]
    solver, ruleset = featured["solver"], featured["ruleset"]
    digest = hashlib.sha256(report_json(report)).hexdigest()
    problems = '<p class="check-ok">检查通过：每个场景的标签与攻击符合预期。</p>' if not report["problems"] else '<ul class="check-failed">' + ''.join(f'<li>{h(problem)}</li>' for problem in report['problems']) + '</ul>'
    others = ''.join(_scenario(scenario, index) for index, scenario in enumerate(report['scenarios']) if index != FEATURED_SCENARIO)
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
<title>PEAD 论证攻防 · 视鉴</title><style>{CSS}</style></head><body><span id="figure" aria-hidden="true"></span>
<header class="masthead"><div><a class="brand" href="#"><svg viewBox="0 0 28 28" aria-hidden="true"><path d="M9 3H4v5M19 3h5v5M24 20v5h-5M9 25H4v-5M9 14h10"/></svg><strong>视鉴</strong><span>VideoGuard-E</span></a><span class="masthead-label">内容安全辅助审核 / 工程验证</span></div></header>
<main><header class="page-heading"><div><h1>证据约束与论证攻防</h1><p>将模型关系候选与结构证据放在一起，核对判断如何形成。</p></div><a class="capture-link" href="#figure">配图视图</a><a class="capture-back" href="#">查看全部工程场景</a></header>
<div class="scope"><span class="scope-symbol">!</span><p><strong>合成测试输入，程序实际求解。</strong>上游观察与关系回答由工程样例预设；本页展示决策机制，不代表真实视频识别效果。</p></div>
{_scenario(featured, FEATURED_SCENARIO, featured=True)}
<div class="provenance"><div><span>求解器</span><b>{h(solver['name'])} {h(solver['version'])}</b><small>{h(solver['distribution'])} · {h(solver['graph_library'])} {h(solver['graph_version'])}</small></div>
<div><span>论证语义</span><b>{h(featured['semantics'])}</b><small>fallback={h(solver['fallback'])}</small></div>
<div><span>规则集</span><b>{h(ruleset['id'])} v{h(ruleset['version'])}</b><small>SHA-256 {h(ruleset['sha256'][:16])}…</small></div></div>
<section class="other-scenarios"><h2>其余工程场景</h2><p class="muted">展开查看同一轮程序计算的其他论证形态。</p>{others}<h2>检查结果</h2>{problems}</section>
<footer><span>工程场景与求解输出可核对：<a href="pead-argumentation.json">下载完整论证记录 JSON</a><small>SHA-256 {digest}</small></span>
<p>由 <code>python -m fixtures.argumentation_html</code> 生成。grounded 标签由完整攻击与防御关系决定；四个样例未出现未决标签，不代表其他输入不会出现。</p></footer></main></body></html>'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="verify the page and data match the current solver output")
    args = parser.parse_args()
    report = build()
    html, data = render(report), report_json(report)
    if args.check:
        if not REPORT.exists() or REPORT.read_text(encoding="utf8") != html or not REPORT_DATA.exists() or REPORT_DATA.read_bytes().replace(b"\r\n", b"\n") != data:
            print("报告页面或数据与当前求解结果不一致；运行 python -m fixtures.argumentation_html")
            return 1
        print("argumentation html and source data are up to date")
        return 1 if report["problems"] else 0
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_bytes(html.encode("utf8"))
    REPORT_DATA.write_bytes(data)
    print(f"已写入 {REPORT} 与 {REPORT_DATA.name}")
    if report["problems"]:
        for problem in report["problems"]:
            print(f"  - {problem}")
        return 1
    print("检查通过：四个工程场景均实际求解，主图展示第二个场景。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

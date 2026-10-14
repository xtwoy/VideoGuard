"""Standalone printable audit report. Escape every user or model-derived value."""
from __future__ import annotations

from html import escape

DIMENSION_LABELS = {
    "audit_coverage": "审核覆盖",
    "evidence_traceability": "证据可追溯性",
    "safety_risk_control": "风险控制状态",
    "context_completeness": "语境完整性",
    "material_completeness": "素材完整性",
    "narrative_structure": "内容结构",
    "hook_clarity": "开头信息建立",
    "subject_presentation": "主体展示",
    "audiovisual_readability": "音视频可读性",
}
VERDICT_LABELS = {
    "PUBLISHABLE": "可进入人工发布复核",
    "NEEDS_REVISION": "需修改后复核",
    "BLOCKED": "存在阻断项",
    "MANUAL_REVIEW": "需人工复核",
}
STATUS_LABELS = {"PASS": "通过", "WARNING": "注意", "FAIL": "未通过", "MANUAL_REVIEW": "人工复核", "NOT_APPLICABLE": "不适用"}
ACTION_LABELS = {"MASK": "遮挡", "REMOVE": "移除", "TRIM": "缩短", "REORDER": "调序", "REPLACE": "替换", "ADD_CONTEXT": "补充语境", "EDIT_TEXT": "修改文字", "EDIT_AUDIO": "编辑音频", "RECORD": "补录", "ADD_MEDIA": "补充素材", "VERIFY": "核验", "MANUAL_REVIEW": "人工复核"}


def h(value: object) -> str:
    return escape(str("" if value is None else value), quote=True)


def tm(milliseconds: object) -> str:
    if type(milliseconds) is not int or milliseconds < 0:
        return "未精确定位"
    seconds = milliseconds // 1000
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def _style(status: object) -> str:
    if status in {"PASS", "PUBLISHABLE"}:
        return "pass"
    if status in {"FAIL", "BLOCKED"}:
        return "fail"
    return "warning"


def ranges(value: object) -> str:
    if not isinstance(value, list) or not value:
        return "<span class=\"muted\">未定位</span>"
    rendered = [
        f"<span class=\"time\">{h(tm(item.get('start_ms')))}—{h(tm(item.get('end_ms')))}</span>"
        for item in value if isinstance(item, dict)
    ]
    return " · ".join(rendered) or "<span class=\"muted\">未定位</span>"


def score_card(name: str, raw: object) -> str:
    item = raw if isinstance(raw, dict) else {}
    status = item.get("status")
    details = item.get("items") if isinstance(item.get("items"), list) else []
    detail_html = "".join(
        f"<li><b>{h(detail.get('label'))}</b> · {h(detail.get('score'))} · "
        f"{h(STATUS_LABELS.get(detail.get('status'), detail.get('status') or '未提供'))}"
        f"<br><span class=\"muted\">{h(detail.get('summary'))}</span><br>{ranges(detail.get('time_ranges'))}</li>"
        for detail in details if isinstance(detail, dict)
    )
    limitations = item.get("limitations") if isinstance(item.get("limitations"), list) else []
    limit_html = "".join(f"<p class=\"muted\">限制：{h(value)}</p>" for value in limitations if isinstance(value, str))
    return f"""<section class="score"><small>{h(DIMENSION_LABELS[name])}</small>
<b class="score-number">{h(item.get('score', '—'))}</b>
<span class="pill {_style(status)}">{h(STATUS_LABELS.get(status, status or '未提供'))}</span>
<p>{h(item.get('summary'))}</p>{f'<ul class="score-details">{detail_html}</ul>' if detail_html else ''}{limit_html}</section>"""


def issue_card(raw: dict) -> str:
    evidence = raw.get("supporting_evidence") if isinstance(raw.get("supporting_evidence"), list) else []
    evidence_html = "".join(
        f"<li><b>{h(item.get('ref'))}</b> · {h(item.get('content'))}<br>{ranges(item.get('time_ranges'))}"
        f"{''.join(f'<br><span class=\"muted\">限制：{h(value)}</span>' for value in item.get('limitations', []) if isinstance(value, str))}</li>"
        for item in evidence if isinstance(item, dict)
    ) or "<li>未提供结构化证据。</li>"
    uncertainty = "".join(
        f"<p class=\"muted\">限制：{h(item)}</p>"
        for item in raw.get("uncertainties", []) if isinstance(item, str)
    )
    return f"""<article class="issue"><span class="priority">{h(raw.get('priority'))}</span> <b>{h(raw.get('title'))}</b>
<p>{h(raw.get('description'))}</p><p>{ranges(raw.get('time_ranges'))}</p>
<ul>{evidence_html}</ul>{uncertainty}</article>"""


def action_card(raw: dict) -> str:
    return f"""<article class="action"><b>{h(ACTION_LABELS.get(raw.get('action'), raw.get('action')))}</b>
<p>{h(raw.get('detail'))}</p><p><b>目标位置：</b>{ranges(raw.get('target_time_ranges'))}</p>
<p><b>验收标准：</b>{h(raw.get('acceptance_criteria'))}</p></article>"""


def plan_card(raw: dict) -> str:
    video = raw.get("video") if isinstance(raw.get("video"), dict) else {}
    issues = raw.get("issues") if isinstance(raw.get("issues"), list) else []
    actions = raw.get("actions") if isinstance(raw.get("actions"), list) else []
    return f"""<section class="plan"><div class="plan-head"><div><h3>{h(raw.get('section') or '审核项')}</h3>
<span class="muted">{h(raw.get('id'))} · {h(raw.get('scope'))}</span></div><div>{ranges(video.get('time_ranges'))}</div></div>
<p>{h(video.get('summary'))}</p><h4>问题定位</h4>{''.join(issue_card(item) for item in issues if isinstance(item, dict))}
<h4>处理动作</h4>{''.join(action_card(item) for item in actions if isinstance(item, dict))}</section>"""


def audit_content(audit: object) -> str:
    if not isinstance(audit, dict):
        return "<h2>审核报告</h2><section class=\"notice\">当前没有可用的结构化审核报告。</section>"
    verdict = audit.get("overall_verdict")
    dimensions = audit.get("dimension_scores") if isinstance(audit.get("dimension_scores"), dict) else {}
    scores = "".join(score_card(name, dimensions.get(name)) for name in DIMENSION_LABELS)
    plans = audit.get("revision_plan") if isinstance(audit.get("revision_plan"), list) else []
    plans_html = "".join(plan_card(item) for item in plans if isinstance(item, dict)) or "<section class=\"plan\">当前没有结构化整改分组。</section>"
    limitations = audit.get("limitations") if isinstance(audit.get("limitations"), list) else []
    limit_html = "".join(f"<li>{h(item)}</li>" for item in limitations if isinstance(item, str)) or "<li>未提供限制说明。</li>"
    return f"""<h2>审核结论</h2><section class="plan"><span class="pill {_style(verdict)}">{h(VERDICT_LABELS.get(verdict, verdict))}</span>
<h3 class="score-title">综合评分：{h(audit.get('overall_score'))}</h3><p>{h(audit.get('executive_summary'))}</p><p><b>处理方向：</b>{h(audit.get('overall_direction'))}</p></section>
<h2>维度评分</h2><div class="scores">{scores}</div><h2>问题定位与整改计划</h2>{plans_html}
<details><summary>报告限制与人工复核提示</summary><ul>{limit_html}</ul></details>"""


def render_html(record: dict) -> str:
    result = record.get("result") if isinstance(record.get("result"), dict) else {}
    findings = result.get("findings") if isinstance(result.get("findings"), list) else []
    meta = result.get("meta") if isinstance(result.get("meta"), dict) else {}
    policy_count = meta.get("policy_count") if type(meta.get("policy_count")) is int else len(findings)
    mode = "合成演示，非真实视频审核" if record.get("mode") == "DEMO" else "模型辅助审核"
    needed = sum(1 for item in findings if isinstance(item, dict) and item.get("disposition") != "NONE")
    css = """
    :root{--ink:#172033;--muted:#667085;--line:#d9dee7;--paper:#fff;--bg:#f7f8fa;--accent:#4f46e5;--red:#b42318;--amber:#b54708;--green:#067647}
    *{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.65 "Microsoft YaHei","Noto Sans SC",system-ui,sans-serif}main{max-width:980px;margin:auto;padding:46px 28px 72px}.eyebrow{font-size:11px;color:var(--accent);font-weight:800;letter-spacing:.13em}h1{font-size:30px;line-height:1.2;margin:8px 0}h2{font-size:21px;margin:34px 0 14px}h3{font-size:16px;margin:0}h4{font-size:13px;margin:16px 0 6px}.meta,.muted,small{font-size:12px;color:var(--muted)}.summary,.scores{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin:22px 0}.scores{grid-template-columns:repeat(3,1fr)}.summary>div,.score,.plan,.notice{background:var(--paper);border:1px solid var(--line);border-radius:8px;padding:16px}.summary small,.score small{display:block}.summary b,.score b{display:block;margin-top:3px;overflow-wrap:anywhere}.score{min-height:125px}.score-number{font-size:27px;line-height:1.1}.score-title{margin:10px 0}.score-details{border-top:1px solid var(--line);margin-top:10px;padding-top:7px}.score-details li{font-size:11px}.pill{display:inline-flex;align-items:center;border-radius:99px;padding:3px 9px;font-size:11px;font-weight:800;background:#eef2ff;color:#3730a3}.pill.fail{background:#fef3f2;color:var(--red)}.pill.warning{background:#fffaeb;color:var(--amber)}.pill.pass{background:#ecfdf3;color:var(--green)}.notice{border-left:3px solid var(--amber);background:#fffaeb}.plan{margin:14px 0 18px;break-inside:avoid}.plan-head{display:flex;justify-content:space-between;gap:14px;align-items:flex-start;flex-wrap:wrap}.issue,.action{margin-top:12px;padding:13px;border-left:3px solid #c7d2fe;background:#f8faff}.action{border-left-color:#6ce9a6;background:#f0fdf4}.issue p,.action p{margin:6px 0}.time{display:inline-block;border-radius:4px;background:#eef2ff;color:#3730a3;font-weight:700;font-size:11px;padding:1px 5px}.priority{font-size:11px;font-weight:800;color:var(--red)}ul{padding-left:20px;margin:6px 0}li{margin:4px 0;overflow-wrap:anywhere}footer{border-top:1px solid var(--line);margin-top:36px;padding-top:14px;color:var(--muted);font-size:12px}@media print{body{background:#fff}main{padding:0 12px}}@media(max-width:640px){main{padding:26px 16px}.summary,.scores{grid-template-columns:1fr}}
    """
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'"><title>{h(record.get('video_name'))} · 视鉴</title><style>{css}</style></head><body><main><div class="eyebrow">VIDEOGUARD-E / AUDIT REPORT</div><h1>视频内容审核报告</h1><p class="meta">{h(mode)} · 审核编号 {h(record.get('id'))} · {h(record.get('created_at'))}</p><div class="summary"><div><small>审核状态</small><b>{h(record.get('status'))}</b></div><div><small>视频名称</small><b>{h(record.get('video_name'))}</b></div><div><small>视频观察覆盖</small><b>{h(result.get('coverage', 'UNKNOWN'))}</b></div><div><small>已评估审核点</small><b>{h(policy_count)} 类</b></div><div><small>需要进一步处理的项目</small><b>{h(needed)} 项</b></div></div><div class="notice"><b>重要说明：</b>本报告用于辅助审核。所有模型观察、时间定位和整改建议均需结合原始视频与适用规范进行人工复核，不构成事实或法律认定。</div><p class="meta">观察限制：{h(result.get('coverage_notes') or '未提供')}</p>{audit_content(result.get('audit_report'))}<footer>审核状态：{h(record.get('status', '-'))} · {h(record.get('error') or '请以原视频和结构化证据为准进行人工核查。')}<p>VideoGuard-E — 辅助审核，不替代人工复核。</p></footer></main></body></html>"""

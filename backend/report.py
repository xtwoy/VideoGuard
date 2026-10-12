"""Standalone printable HTML report. Escape every value from users and models."""
from html import escape

def h(value):
    return escape(str("" if value is None else value), quote=True)

def tm(ms):
    if type(ms) is not int or ms < 0:
        return "未精确定位"
    s=ms//1000
    return f"{s//60:02d}:{s%60:02d}"

def render_html(record):
    result=record.get("result") or {}
    evidence=result.get("observations") or []
    findings=result.get("findings") or []
    event_findings=result.get("event_findings") or []
    recommendations=result.get("recommendations") or []
    meta=result.get("meta") or {}
    policy_count=meta.get("policy_count")
    if type(policy_count) is not int or policy_count < 0:
        policy_count=len(findings)
    by_id={str(e.get("id")):e for e in evidence if isinstance(e,dict)}
    by_policy={str(x.get("finding_id")):x for x in recommendations if isinstance(x,dict)}
    names={
        "SUPPORTED":"疑似风险","NOT_SUPPORTED":"暂无证据","INSUFFICIENT":"证据不足",
        "CONFLICTED":"语境冲突","UNKNOWN":"无法判断",
        "FLAG":"标注关注","NONE":"暂无动作","REVIEW":"人工复核",
        "VERIFY_EXTERNAL":"外部核验","RECHECK":"补充观察","RETRY":"重试"
    }
    policy_names={
        "R_DANGER_PROMOTION":"危险行为诱导",
        "R_VIOLENCE":"暴力或危险行为画面",
        "R_PRIVACY_EXPOSURE":"个人隐私暴露",
        "R_MARKETING_CLAIM":"营销及资质声称",
        "R_SELF_HARM":"自伤风险",
        "R_SEXUAL_CONTENT":"性内容风险",
        "R_HATE_HARASSMENT":"仇恨与骚扰",
        "R_FRAUD_SCAM":"诈骗与高风险诱导",
        "R_CONTROLLED_GOODS":"受控商品风险",
        "R_MINORS_PROTECTION":"未成年人保护"
    }
    reason_names={
        "RELATED_ACTION_AND_PROMOTION":"危险动作与鼓励或挑战内容指向同一事件。",
        "CONFLICTING_STANCE":"同一事件同时存在鼓励与警示信息，需要人工核对具体语境。",
        "MISSING_SEMANTIC_RELATION":"观察到相关线索，但无法确认它们是否指向同一事件。",
        "UNLOCATED_PROMOTION":"观察到可能的鼓励内容，但缺少可靠时间位置。",
        "JEV_UNAVAILABLE_SEMANTIC_REVIEW":"关键语义关系尚未完成自动核验，需要人工复核。",
        "JEV_DISPUTES_BASELINE_SUPPORT":"自动分析对原有支持关系存在分歧，需要人工复核。",
        "JEV_NO_CONFIRMED_SEMANTIC_LINK":"未能确认危险动作与相关表述存在明确关联。",
        "JEV_SEMANTIC_AMBIGUITY":"相关表述的语义存在歧义，需要人工复核。",
        "OMNI_JEV_REFERENT_DISAGREEMENT":"不同观察对所指事件存在分歧，需要人工复核。",
        "VIOLENCE_DEPICTION":"观察到疑似暴力或危险行为画面。",
        "DEPICTION_WITH_CONTEXT":"观察到相关画面，同时存在新闻、影视或教育等语境线索。",
        "POTENTIAL_PII":"观察到可能包含个人隐私的信息。",
        "CREDENTIAL_AUTHENTICITY_UNKNOWN":"观察到资质声称，真实性需要外部材料核验。",
        "MARKETING_CLAIM_NEEDS_CONTEXT":"观察到营销或绝对化表述，需要结合上下文核对。",
        "SELF_HARM_CUE":"观察到可能涉及自伤、自杀或相关方法传播的内容线索。",
        "SEXUAL_CONTENT_CUE":"观察到可能不适宜的性内容或性暗示线索。",
        "HATE_HARASSMENT_CUE":"观察到可能涉及仇恨、歧视、侮辱或定向骚扰的内容线索。",
        "FRAUD_SCAM_CUE":"观察到可能涉及诈骗、冒充、虚假获利或高风险交易诱导的内容线索。",
        "CONTROLLED_GOODS_CUE":"观察到可能涉及受控商品展示、交易或引导的内容线索。",
        "MINOR_PROTECTION_CUE":"观察到可能涉及未成年人不适宜、剥削或人身安全风险的内容线索。",
        "UNVERIFIED_OR_UNLOCATED":"存在相关线索，但证据未能可靠定位。",
        "UNLOCATED_PII":"存在隐私暴露线索，但证据未能可靠定位。",
        "UNLOCATED_MARKETING_CLAIM":"存在营销或资质声称线索，但证据未能可靠定位。",
        "INCOMPLETE_OBSERVATION":"视频观察不完整，需要补充核查。",
        "MODEL_UNAVAILABLE":"自动审核未能完成，需要重新执行。"
    }
    event_html = ""
    if event_findings:
        event_html = '<h2>事件级审计记录</h2><div class="events">' + "".join(
            f"<div><b>{h(policy_names.get(e.get('policy_id'), '内容安全问题'))}</b><br>"
            f"{h(names.get(e.get('judgement'), e.get('judgement')))} / "
            f"{h(names.get(e.get('disposition'), e.get('disposition')))} · "
            f"证据: {h(','.join(e.get('evidence_ids', [])))}</div>"
            for e in event_findings if isinstance(e, dict)
        ) + "</div>"

    cards=[]
    for finding in findings:
        if finding.get("disposition")=="NONE":
            continue
        policy=str(finding.get("policy_id",""))
        ids=list(dict.fromkeys(finding.get("supporting_ids",[])+finding.get("counter_ids",[])))
        proof=[]
        for eid in ids:
            item=by_id.get(str(eid))
            if item is None:
                proof.append(f"<li>引用不存在：{h(eid)}</li>")
                continue
            description=item.get("description_redacted") or item.get("text_redacted") or "无描述"
            proof.append(
                f"<li><strong>{h(tm(item.get('start_ms')))}—{h(tm(item.get('end_ms')))}</strong> "
                f" · {h(eid)} · {h(item.get('modality'))} · {h(description)}"
                "<small>模型观察，尚未人工核实</small></li>"
            )
        note=by_policy.get(policy,{})
        edits=note.get("edit_suggestions") or []
        edits_html="".join(
            "<li>"+h(item.get("detail",""))+"</li>"
            for item in edits if isinstance(item,dict)
        ) or "<li>建议人工回看相关片段。</li>"
        decision=names.get(finding.get("judgement"),"无法判断")
        action=names.get(finding.get("disposition"),"人工复核")
        cards.append(f"""
        <section class="finding">
          <div class="head"><h3>{h(finding.get("name") or policy_names.get(policy, '内容安全问题'))}</h3>
            <span class="pill">{h(decision)} / {h(action)}</span>
          </div>
          <p class="sub">{h(reason_names.get(finding.get("reason_code"), "请结合对应证据和原视频进行人工核对。"))}</p>
          <h4>可回溯证据</h4>
          <ul>{"".join(proof) or "<li>无可靠可定位证据</li>"}</ul>
          <h4>原因与修改建议</h4>
          <p>{h(reason_names.get(note.get("reason"), note.get("reason") or "本结论需结合原片段核查。"))}</p>
          <ul>{edits_html}</ul>
        </section>
        """)
    if not cards:
        cards=['<section class="finding">审核尚未生成有效风险结果。</section>']
    mode="合成演示，并非真实视频审核" if record.get("mode")=="DEMO" else "真实模型审核"
    css="""
    :root{--ink:#1f3936;--teal:#237c6c;--line:#dbe2dc}
    *{box-sizing:border-box}body{margin:0;background:#f7f5ef;color:var(--ink);
      font:15px/1.65 "Microsoft YaHei","Noto Sans SC",system-ui,sans-serif}
    main{max-width:860px;margin:auto;padding:48px 28px 72px}
    .eyebrow{font-size:11px;color:var(--teal);font-weight:750;letter-spacing:.16em}
    h1{font-size:32px;line-height:1.2;margin:8px 0}
    h2{font-size:21px;margin-top:34px}
    .sub,.meta,small{color:#698078;font-size:12px}
    .summary{display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin:25px 0}
    .summary div,.finding{border:1px solid var(--line);border-radius:12px;
      background:#fff;padding:18px 20px}
    .summary small{display:block}.summary b{overflow-wrap:anywhere}
    .finding{margin:15px 0 20px;break-inside:avoid}
    .events{display:grid;gap:9px}.events div{border-left:3px solid #7aa492;background:#f5f8f5;
      padding:10px 13px;color:#506b60;font-size:12px;overflow-wrap:anywhere}
    .head{display:flex;align-items:center;gap:16px;justify-content:space-between;flex-wrap:wrap}
    h3{margin:0;font-size:19px}h4{font-size:14px;margin:18px 0 6px}
    .pill{border-radius:99px;background:#e8f3ee;color:#236e62;padding:4px 10px;
      font-size:12px;font-weight:700}
    ul{padding-left:20px;margin:5px 0}li{margin:5px 0;overflow-wrap:anywhere}
    li small{display:block}.notice{background:#fff4e3;border-left:3px solid #d59b45;padding:15px}
    footer{border-top:1px solid var(--line);margin-top:32px;padding-top:14px;
      color:#718078;font-size:12px}
    @media print{body{background:white}main{padding:0 12px}}
    @media(max-width:540px){main{padding:24px 16px}.summary{grid-template-columns:1fr}}
    """
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
<title>{h(record.get("video_name",""))} · 视鉴</title>
<style>{css}</style></head><body><main>
<div class="eyebrow">VIDEOGUARD-E / CONTENT SAFETY REPORT</div>
<h1>视频内容安全审核报告</h1>
<p class="meta">{h(mode)} · 审核编号 {h(record.get("id",""))} · {h(record.get("created_at",""))}</p>
<div class="summary">
 <div><small>审核状态</small><b>{h(record.get("status",""))}</b></div>
 <div><small>视频名称</small><b>{h(record.get("video_name",""))}</b></div>
 <div><small>视频观察覆盖</small><b>{h(result.get("coverage","UNKNOWN"))}</b></div>
 <div><small>已评估审核点</small><b>{h(policy_count)} 类</b></div>
 <div><small>需要进一步处理的项目</small><b>{sum(1 for f in findings if f.get("disposition") != "NONE")}</b></div>
</div>
<div class="notice"><b>重要说明：</b> 本报告只作内容安全辅助审核参考。
证据描述、时间戳和模型判断可能存在错误；不能据此自动认定违法，
对风险结论必须结合原始视频及适用规范进行人工核查。</div>
<p class="meta">观察说明：{h(result.get("coverage_notes") or "未提供")}</p>
<h2>风险结果与修改建议</h2>
{"".join(cards)}
{event_html}
<footer>审核状态：{h(record.get("status","-"))} · {h(record.get("error","") or "请以原视频和可回溯证据为准进行人工核查。")}
<p>VideoGuard-E — 辅助审核，不代替人工复核。</p></footer>
</main></body></html>"""

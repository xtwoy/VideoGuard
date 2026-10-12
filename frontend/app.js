"use strict";
// Default local API is 8000. The optional api query parameter supports
// isolated previews when another local service already owns that port.
const API = new URLSearchParams(window.location.search).get("api") || "http://127.0.0.1:8000";
const $ = (id) => document.getElementById(id);
const riskLabels = {
  SUPPORTED:"疑似风险", NOT_SUPPORTED:"暂无证据", INSUFFICIENT:"证据不足",
  CONFLICTED:"语境冲突", UNKNOWN:"无法判断",
  FLAG:"标注关注", NONE:"暂无动作", REVIEW:"人工复核",
  VERIFY_EXTERNAL:"外部核验", RECHECK:"补充观察", RETRY:"需要重试"
};
const policyLabels = {
  R_DANGER_PROMOTION:"危险行为诱导",
  R_VIOLENCE:"暴力或危险行为画面",
  R_PRIVACY_EXPOSURE:"个人隐私暴露",
  R_MARKETING_CLAIM:"营销及资质声称",
  R_SELF_HARM:"自伤风险",
  R_SEXUAL_CONTENT:"性内容风险",
  R_HATE_HARASSMENT:"仇恨与骚扰",
  R_FRAUD_SCAM:"诈骗与高风险诱导",
  R_CONTROLLED_GOODS:"受控商品风险",
  R_MINORS_PROTECTION:"未成年人保护"
};
const coverageLabels = {
  FULL:"覆盖完整", PARTIAL:"覆盖不完整", UNKNOWN:"覆盖情况未知",
  REFUSED:"未能完成审核", ERROR:"审核执行失败"
};
const reasonLabels = {
  RELATED_ACTION_AND_PROMOTION:"危险动作与鼓励或挑战内容指向同一事件。",
  CONFLICTING_STANCE:"同一事件同时存在鼓励与警示信息，需要人工核对具体语境。",
  MISSING_SEMANTIC_RELATION:"观察到相关线索，但无法确认它们是否指向同一事件。",
  UNLOCATED_PROMOTION:"观察到可能的鼓励内容，但缺少可靠时间位置。",
  JEV_UNAVAILABLE_SEMANTIC_REVIEW:"关键语义关系尚未完成自动核验，需要人工复核。",
  JEV_DISPUTES_BASELINE_SUPPORT:"自动分析对原有支持关系存在分歧，需要人工复核。",
  JEV_NO_CONFIRMED_SEMANTIC_LINK:"未能确认危险动作与相关表述存在明确关联。",
  JEV_SEMANTIC_AMBIGUITY:"相关表述的语义存在歧义，需要人工复核。",
  OMNI_JEV_REFERENT_DISAGREEMENT:"不同观察对所指事件存在分歧，需要人工复核。",
  VIOLENCE_DEPICTION:"观察到疑似暴力或危险行为画面。",
  DEPICTION_WITH_CONTEXT:"观察到相关画面，同时存在新闻、影视或教育等语境线索。",
  POTENTIAL_PII:"观察到可能包含个人隐私的信息。",
  CREDENTIAL_AUTHENTICITY_UNKNOWN:"观察到资质声称，真实性需要外部材料核验。",
  MARKETING_CLAIM_NEEDS_CONTEXT:"观察到营销或绝对化表述，需要结合上下文核对。",
  SELF_HARM_CUE:"观察到可能涉及自伤、自杀或相关方法传播的内容线索。",
  SEXUAL_CONTENT_CUE:"观察到可能不适宜的性内容或性暗示线索。",
  HATE_HARASSMENT_CUE:"观察到可能涉及仇恨、歧视、侮辱或定向骚扰的内容线索。",
  FRAUD_SCAM_CUE:"观察到可能涉及诈骗、冒充、虚假获利或高风险交易诱导的内容线索。",
  CONTROLLED_GOODS_CUE:"观察到可能涉及受控商品展示、交易或引导的内容线索。",
  MINOR_PROTECTION_CUE:"观察到可能涉及未成年人不适宜、剥削或人身安全风险的内容线索。",
  UNVERIFIED_OR_UNLOCATED:"存在相关线索，但证据未能可靠定位。",
  UNLOCATED_PII:"存在隐私暴露线索，但证据未能可靠定位。",
  UNLOCATED_MARKETING_CLAIM:"存在营销或资质声称线索，但证据未能可靠定位。",
  INCOMPLETE_OBSERVATION:"视频观察不完整，需要补充核查。",
  MODEL_UNAVAILABLE:"自动审核未能完成，需要重新执行。"
};
let previewUrl = null;
let chosenFile = null;

function refreshIcons() {
  if (window.lucide) window.lucide.createIcons();
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = String(text);
  return node;
}
function setStatus(message, isError = false) {
  const status = $("status");
  status.hidden = !message;
  status.className = "status" + (isError ? " error" : "");
  status.textContent = message || "";
}
function setReviewError(message, reviewId) {
  setStatus("", true);
  const status = $("status");
  status.hidden = false;
  status.append(document.createTextNode(message));
  if (reviewId) {
    const link = el("a","status-report-link","查看失败记录与 HTML 报告 ↗");
    link.href = `${API}/api/reviews/${encodeURIComponent(reviewId)}/report`;
    link.target = "_blank";
    link.rel = "noopener";
    status.append(link);
  }
}
function formatTime(ms) {
  if (!Number.isInteger(ms) || ms < 0) return "未定位";
  const sec = Math.floor(ms / 1000);
  return `${String(Math.floor(sec / 60)).padStart(2,"0")}:${String(sec % 60).padStart(2,"0")}`;
}
function policyName(finding) {
  return finding.name || policyLabels[finding.policy_id] || "内容安全问题";
}
function reasonText(reasonCode) {
  return reasonLabels[reasonCode] || "请结合对应证据和原视频进行人工核对。";
}
function attachFile(file) {
  if (previewUrl) URL.revokeObjectURL(previewUrl);
  chosenFile = file || null;
  $("file-name").textContent = chosenFile ? chosenFile.name : "点击选择短视频";
  $("file-detail").textContent = chosenFile ?
    `${(chosenFile.size / 1000000).toFixed(2)} MB · 上传前可预览` :
    "MP4 / MOV / WebM · 最大 6 MB · 3 分钟内";
  $("video-preview").hidden = !chosenFile;
  $("media-empty").hidden = Boolean(chosenFile);
  $("media-state").textContent = chosenFile ? "已选择视频" : "尚未选择";
  $("media-caption-text").textContent = chosenFile ?
    `${chosenFile.name} · ${(chosenFile.size / 1000000).toFixed(2)} MB · 可在审核结果中回看片段` :
    "支持 MP4、MOV、WebM；文件不超过 6 MB，时长不超过 3 分钟。";
  if (chosenFile) {
    previewUrl = URL.createObjectURL(chosenFile);
    $("video-preview").src = previewUrl;
  } else {
    $("video-preview").removeAttribute("src");
    previewUrl = null;
  }
}
function render(record) {
  const result = record.result || {};
  $("results").hidden = false;
  $("audit-empty").hidden = true;
  $("report-link").hidden = false;
  if (record.mode === "DEMO") {
    $("media-state").textContent = "合成示例";
    $("media-caption-text").textContent = "当前展示的是合成审核数据；未关联原视频，因此证据回看不可用。";
  }
  $("result-subtitle").textContent =
    `${record.video_name} · ${record.mode === "DEMO" ? "合成示例，非真实视频分析" : "模型辅助审核"}`;
  $("report-link").href = `${API}/api/reviews/${encodeURIComponent(record.id)}/report`;

  const meta = $("result-meta");
  meta.replaceChildren();
  const findingsForSummary = result.findings || [];
  const policyCount = Number.isInteger(result.meta?.policy_count) ?
    result.meta.policy_count : Object.keys(policyLabels).length;
  const attentionCount = findingsForSummary.filter(f => f.disposition === "FLAG").length;
  const reviewCount = findingsForSummary.filter(f =>
    ["REVIEW","VERIFY_EXTERNAL","RECHECK","RETRY"].includes(f.disposition)).length;
  [
    `已评估：${policyCount} 类`,
    `审核范围：${coverageLabels[result.coverage] || "覆盖情况未知"}`,
    `标注关注：${attentionCount} 项`,
    `需进一步处理：${reviewCount} 项`
  ].forEach(t => meta.appendChild(el("span","smalltag",t)));

  const coverageNotes = $("coverage-notes");
  coverageNotes.hidden = !result.coverage_notes;
  coverageNotes.textContent = result.coverage_notes || "";

  const findings = $("findings");
  findings.replaceChildren();
  (result.findings || []).filter(f => f.disposition !== "NONE").forEach(f => {
    const card = el("article","finding");
    const top = el("div","finding-top");
    top.append(el("strong",null,policyName(f)));
    const label = el("span","risk-pill",`${riskLabels[f.judgement] || f.judgement}`);
    if (f.disposition === "FLAG") label.classList.add("alert");
    else if (f.disposition !== "NONE") label.classList.add("review");
    top.append(label);
    card.append(top,el("p",null,
      `${reasonText(f.reason_code)} 处理建议：${riskLabels[f.disposition] || "人工复核"}。`));
    findings.append(card);
  });
  if (!findings.children.length) findings.append(el("p","muted","当前没有可用的规则判断。"));

  const events = $("event-findings");
  events.replaceChildren();
  (result.event_findings || []).forEach(event => {
    const card = el("article","event-finding");
    const top = el("div","event-top");
    top.append(el("strong",null,policyLabels[event.policy_id] || "事件审计"));
    top.append(el("span","risk-pill",
      `${riskLabels[event.judgement] || event.judgement || "-"} · ${riskLabels[event.disposition] || event.disposition || "-"}`));
    const ids = Array.isArray(event.evidence_ids) ? event.evidence_ids.join("、") : "无";
    card.append(top,el("p",null,`关联证据：${ids}`));
    card.append(el("small",null,reasonText(event.reason_code)));
    events.append(card);
  });
  if (!events.children.length) events.append(el("p","muted","当前没有可单独审计的事件记录。"));

  const evidence = $("evidence");
  evidence.replaceChildren();
  (result.observations || []).forEach(e => {
    const row = el("div","evidence-row");
    const group = el("div");
    group.append(el("b",null,`${e.id} · ${formatTime(e.start_ms)}—${formatTime(e.end_ms)}`));
    group.append(el("p",null,e.description_redacted || e.text_redacted || "未提供描述"));
    group.append(el("small",null,`${e.modality} · 模型观察，未经人工核实`));
    const btn = el("button","time-btn","回看片段 ↗");
    btn.type = "button";
    btn.disabled = !chosenFile || record.mode === "DEMO" ||
                   !Number.isInteger(e.start_ms);
    btn.addEventListener("click",() => {
      const video = $("video-preview");
      video.currentTime = e.start_ms / 1000;
      video.scrollIntoView({behavior:"smooth",block:"center"});
      video.play().catch(()=>{});
    });
    row.append(group,btn);
    evidence.append(row);
  });
  if (!evidence.children.length) evidence.append(el("p","muted","没有可回溯的观察证据。"));

  const suggestions = $("recommendations");
  suggestions.replaceChildren();
  (result.recommendations || []).forEach(item => {
    const wrap = el("div","suggestion");
    wrap.append(el("b",null,
      `整改建议 · ${policyLabels[item.finding_id] || "相关风险"}`));
    if (item.reason) wrap.append(el("p",null,reasonText(item.reason)));
    (item.edit_suggestions || []).forEach(a => {
      wrap.append(el("p",null,`• ${a.detail || "建议人工核验"}`));
    });
    suggestions.append(wrap);
  });
  if (!suggestions.children.length) suggestions.append(el("p","muted","当前无新增整改建议。"));
  refreshIcons();
  $("results").scrollIntoView({behavior:"smooth",block:"start"});
}
async function post(url, body) {
  const response = await fetch(API + url,{method:"POST",body});
  let data;
  try {
    data = await response.json();
  } catch {
    throw new Error(`服务器返回了无法解析的响应（${response.status}）`);
  }
  if (!response.ok) {
    const details = data.detail;
    const error = new Error(typeof details === "string" ? details :
      details?.message || `服务器错误 ${response.status}`);
    error.reviewId = typeof details === "object" ? details?.review_id : null;
    throw error;
  }
  return data;
}
async function busy(operation) {
  $("submit-btn").disabled = true;
  $("demo-btn").disabled = true;
  $("results").hidden = true;
  $("audit-empty").hidden = true;
  $("report-link").hidden = true;
  setStatus("正在分析视频内容、核对可回溯证据并生成整改建议。请保持页面打开。");
  try {
    const record = await operation();
    setStatus(record.mode === "DEMO" ?
      "合成示例已生成，以下不是实际视频检测结果。" :
      "审核完成。请回看相关视频片段，并下载HTML报告。");
    render(record);
  } catch (error) {
    setReviewError(error?.message || "请求失败，请检查后端服务。",error?.reviewId);
    $("audit-empty").hidden = false;
  } finally {
    $("submit-btn").disabled = false;
    $("demo-btn").disabled = false;
  }
}
$("video-file").addEventListener("change",(event)=>{
  attachFile(event.target.files?.[0] || null);
});
$("review-form").addEventListener("submit",(event)=>{
  event.preventDefault();
  if (!chosenFile) return setStatus("请选择视频文件。",true);
  if (chosenFile.size > 6000000) return setStatus("视频超过6MB，请压缩后重试。",true);
  if (!$("consent").checked) return setStatus("请先确认素材已经授权。",true);
  const data = new FormData();
  data.append("video", chosenFile);
  data.append("title", $("video-title").value);
  data.append("consent", "true");
  busy(()=>post("/api/reviews",data));
});
$("demo-btn").addEventListener("click",()=>busy(()=>post("/api/demo")));
refreshIcons();
fetch(API + "/api/health")
  .then(res => {
    if (!res.ok) throw new Error("unavailable");
    $("server-state").textContent="本地审核服务已连接";
  }).catch(()=>{
    $("server-state").textContent="无法连接后端，请先启动8000端口";
    $("server-state").parentElement.querySelector(".dot").style.background="#d69b67";
  });

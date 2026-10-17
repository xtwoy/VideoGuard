# 视频解析任务

请完整观看该视频，并按 `videoguard_video_parse_v2` 输出结构化事实。

本次任务优先级：

1. 完整建立无遗漏的镜头时间线；
2. 将可观察事实、口播、字幕、屏幕文字和声音观察逐条记录到所属 shot；
3. 为每一条事实写入位于 shot 内的 `start_ms` / `end_ms`；
4. 使用 `SHOT_ID:FACT_ID` 将事件、质量观察和音画可读性问题回链到原始事实；
5. 为 `video_summary` 和 `content_analysis.audio_visual_quality` 补齐 `evidence_refs`、`time_ranges`、`limitations`；不能只写摘要文字；
6. 只描述视频实际内容，不输出风险标签、政策判断、发布结论或修改建议。

重点保留：动作及其语境、冲突或危险画面、可辨认文字、营销或资质声称、交易和获利引导、疑似隐私文字、警示/新闻/影视/教育/引用语境，以及影响识别的音画限制。

视频标题：`{{VIDEO_TITLE}}`

原视频长度（毫秒）：`{{DURATION_MS}}`

时间不可靠、画面/声音不完整或内容无法辨识时，请记录限制，不得猜测。只输出 JSON。

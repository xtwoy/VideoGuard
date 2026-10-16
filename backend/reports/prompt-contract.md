# Prompt 契约检查

> 由 `python -m fixtures.prompt_contract --write` 生成，请勿手工编辑。

静态契约检查：prompt 要求的字段与枚举是否被代码接受。不检查模型是否遵循 prompt——那需要真实调用。

| 阶段 | 检查项 | 结论 | 说明 |
| --- | --- | --- | --- |
| video_parse | coverage.modalities 的键 | 通过 |  |
| video_parse | 枚举 events[].context.target_relation | 通过 |  |
| video_parse | 枚举 coverage.status | 通过 |  |
| video_parse | 枚举 coverage.time_localization | 通过 |  |
| video_parse | 枚举 coverage.modalities.* | 通过 |  |
| video_parse | 枚举 shots[].continuity | 通过 |  |
| video_parse | 枚举 facts[].confidence | 通过 |  |
| video_parse | 枚举 quality.visual_clarity | 通过 |  |
| video_parse | 枚举 quality.speech_clarity | 通过 |  |
| video_parse | 枚举 quality.audio.status | 通过 |  |
| video_parse | 枚举 quality.audio.voice_clarity | 通过 |  |
| video_parse | 枚举 quality.audio.bgm_interference | 通过 |  |
| video_parse | 枚举 quality.visual.clarity | 通过 |  |
| video_parse | 枚举 quality.visual.pixelation | 通过 |  |
| video_parse | 枚举 quality.visual.aliasing_candidate | 通过 |  |
| video_parse | 枚举 events[].context.stance | 通过 |  |
| video_parse | 必填顶层字段 schema_version | 通过 |  |
| video_parse | 必填顶层字段 coverage | 通过 |  |
| video_parse | 必填顶层字段 timeline | 通过 |  |
| video_parse | 必填顶层字段 video_summary | 通过 |  |
| video_parse | 必填顶层字段 content_analysis | 通过 |  |
| video_parse | content_analysis.material_completeness 存在 | 通过 |  |
| video_parse | content_analysis.structure 存在 | 通过 |  |
| video_parse | content_analysis.hook 存在 | 通过 |  |
| video_parse | content_analysis.subject_presentation 存在 | 通过 |  |
| video_parse | content_analysis.audio_visual_quality 存在 | 通过 |  |
| issue_locator | 适配器标签词表与 PEAD 的 VALID_TAGS 兼容 | 通过 |  |
| issue_locator | schema 要求的字段与协议一致 | 通过 |  |
| relation_check | 四类语义选择都在 system prompt 中说明 | 通过 |  |
| relation_check | schema 协议版本 | 通过 |  |
| audit_report | 九维度与校验器一致 | 通过 |  |
| audit_report | 枚举 overall_verdict | 通过 |  |
| audit_report | 整改动作词表与校验器一致 | 通过 |  |
| audit_report | 维度状态词表与校验器一致 | 通过 |  |

## 说明

本检查是**静态**的：它保证 prompt 要求的字段与枚举都被校验器接受，从而排除真实调用时因契约不一致而必然失败的整类问题。它不能证明模型会遵循 prompt——那只能由一次真实调用回答。

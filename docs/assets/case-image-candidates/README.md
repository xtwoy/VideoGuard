# 场景配图候选与生成记录

日期：2026-10-21。使用内置 imagegen 工具生成；用户确认后已接入开发预览的配图配置，手机图选用 v4，其余三图沿用本目录版本。

这些图片为按案例情境生成的场景插图，不是原视频帧，不参与冻结案例结论生成。图片内部不添加样卡、示例等解释文字；来源记录保存在此文件。

| 文件 | 对应画面 |
|---|---|
| [01-phone-id-v4.png](01-phone-id-v4.png) | 手机屏幕中的证件信息暴露，横向正常卡片比例；v2 保留作历史候选 |
| [02-rooftop.png](02-rooftop.png) | 翻越天台护栏跨楼 |
| [03-kitchen.png](03-kitchen.png) | 手撑灶台跳过燃烧灶眼 |
| [04-cycling.png](04-cycling.png) | 跨事件案例的独立户外骑行场景 |

手机图使用虚构人物与道具信息，移除了初版的样卡标题、样例括注和全零号码；基于初版照片编辑，保留桌面、手和手机构图。候选图不覆盖原文件。

生成提示词如下。

## 01-phone-id-v2.png

```text
Use case: precise-object-edit.
Edit target: the supplied wide photograph of a hand holding a smartphone at an unboxing desk. Keep the original landscape 16:9 composition, hand anatomy, phone shape, desk, cardboard box, laptop, lighting, portrait photograph, screen perspective and all background elements unchanged.
Change ONLY the document photo displayed on the phone screen:
1. Remove the entire top text “样卡·虚构信息”, leaving a clean continuation of the card's subtle pale blue security-pattern background in that area. No replacement heading.
2. Replace the name “张三（样例）” with the ordinary fictional name “周明远”. No parentheses or qualifiers.
3. Replace the all-zero identity-number string with this invented nonfunctional prop string: “32010619940718061X”. Replace the birth-date field with “1994 年 7 月 18 日”. Use ordinary restrained printed card typography integrated naturally into the photographed screen.
4. The address should read “江苏省南京市鼓楼区云杉路18号”. These are invented character details for scene illustration, not a real person's identity record.
Do not put “样例”, “示例”, “虚构”, “样卡”, “DEMO”, “SAMPLE”, disclaimers or any other explanatory banner anywhere in the visible picture. Do not add an official seal, state emblem, barcode or QR code.
Keep natural screen softness, subtle reflections and believable photographic details; avoid exaggerated vector-sharp text or a poster/mockup look. No red annotation rectangle, no arrows, no new overlays, no watermark.
```

## 02-rooftop.png

```text
Use case: photorealistic-natural.
Asset type: standalone 16:9 landscape scene illustration for a short-video dangerous-action review case.
Primary request: precisely illustrate “男子翻越天台护栏，跨过两栋楼之间的空隙”.
Scene: dense contemporary residential buildings, overcast daylight, two adjacent flat concrete rooftops separated by a clearly visible narrow gap. Distant streets and building walls below establish that this is high above ground.
Subject: one fictional adult man in ordinary dark navy sports clothing and sneakers, fully visible, captured mid-leap across the gap from one rooftop toward the neighboring rooftop. His trailing foot has just left the takeoff ledge and his leading leg reaches toward the receiving roof, anatomically plausible athletic motion.
Composition: wide documentary frame, side/three-quarter view from a nearby rooftop, approximately 35mm lens. Both takeoff and landing roof edges are visible. A plain metal guardrail runs along the takeoff terrace behind and to the side of him, establishing that he has crossed its boundary. Keep the human subject in the central half of the frame with room around the entire body so the action is readable at thumbnail size.
Style: sober editorial reconstruction of a risky stunt, believable photographic textures, natural gray concrete and cool city colors, crisp human silhouette, daylight, realistic scale and perspective. Unbranded contemporary Chinese urban setting.
Constraints: single full-bleed image; no infographic, no split panels, no UI, no video controls, no arrows or detection boxes, no subtitles, no logos, no watermarks. No injuries, no fall, no blood. Do not glamorize it with victory poses, celebratory spectators, advertising or heroic effects. Do not substitute ground-level playground parkour.
```

## 03-kitchen.png

```text
Use case: photorealistic-natural. Single full-bleed 16:9 landscape image of an ordinary modern kitchen. One adult man in a dark tee, gray sports trousers and sneakers is captured mid-vault over a lit gas cooktop, one hand visibly planted on the countertop edge, his bent legs above the burner flame. Show the full person, hand contact, countertop and small blue-orange gas flame together in a believable side/three-quarter composition. Physically plausible anatomy and kitchen proportions, restrained daylight, documentary action still. Match the short-video case “厨房内男子撑灶台跳过燃烧的灶眼”. No other people, no UI, no text, no labels, no arrows, no red boxes, no watermarks, no injury, no explosion, no heroic effects.
```

## 04-cycling.png

```text
Use case: photorealistic-natural.
Asset type: a single standalone landscape 16:9 scene photograph-style illustration for a short-video safety-review case.
Primary request: illustrate the second scene in the case “厨房危险动作后切到户外骑行，骑手提醒不要模仿”. This image must clearly show the independent outdoor cycling setting, not a kitchen and not a composite.
Scene/backdrop: a quiet paved suburban road in daylight, green roadside trees, low distant hills, subtle pale sky. Natural contemporary East Asian surroundings, no location landmark or branding.
Subject: one fictional adult East Asian male cyclist, wearing a correctly fastened ordinary helmet, muted navy cycling top and dark cycling shorts, riding a dark road bicycle. He glances briefly toward a camera traveling alongside. Hands remain on the handlebars, believable balanced riding pose. Show the complete bicycle, both wheels, rider's head, hands and legs with comfortable margins.
Composition: medium-wide three-quarter side view from approximately bicycle height, subject occupies the central two-thirds, road and vegetation clearly readable behind him. Photographic realism, moderate background depth of field, realistic anatomy, plausible bike geometry, restrained natural cool daylight.
Constraints: image should read as an ordinary frame from a filmed ride, not an advertisement or an extreme sport stunt. No dangerous traffic maneuver, no crash, no injuries, no extra riders, no speech bubble, no quotation or fake subtitle, no UI, no playback controls, no red boxes or arrows, no logo, no watermark, no explanation labels.
```


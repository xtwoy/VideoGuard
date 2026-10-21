
## 01-phone-id-v4.png

使用内置 imagegen 对手机屏幕内的证件图片做局部编辑。正常横向卡片长宽约 1.59∶1，保留手机与桌面构图，重新排布头像及文字。v3 检查后仍偏高，v4 再降低卡片高度；以下保留两步提示词。

### 首次比例修正

```text
Use case: precise-object-edit.
Edit target: the supplied 16:9 landscape photograph of a hand holding a smartphone at an unboxing desk.
Primary correction: the identity card photo INSIDE the smartphone screen is currently almost square and has visibly wrong proportions. Replace that card image with a correctly proportioned horizontal ID-1 card: physical width 85.6 mm, height 54 mm, exact width-to-height ratio approximately 1.586:1 before perspective. It must look like a normal compact landscape Chinese resident identity card viewed in a phone's photo viewer.

Change ONLY the content within the phone screen. Preserve the original phone, entire hand, fingers, desk, laptop, parcel, cup, background, lens perspective, daylight and 16:9 framing.
Specific geometry:
- Keep the card centered horizontally on the phone screen, fully visible with a small margin at both sides.
- Retain approximately its current card WIDTH, but reduce its HEIGHT by around one third so that it becomes a proper 1.586:1 landscape rectangle. The remaining screen above and below is plain black photo-viewer space.
- Respect the same subtle screen perspective/tilt. Do not turn the card upright or make it square. Do not stretch the phone or fill the screen vertically.
- Recompose all card content to fit a genuine compact card layout: short tightly spaced identity field rows on the left, small correctly proportioned portrait on the right, identity-number row across the bottom. Eliminate the large empty header area. Fit the entire card's rounded boundary in frame. Do not squash the portrait or stretch text to change the aspect ratio.
Preserve the existing fictional character details and portrait as closely as possible, including name “周明远”, birth date “1994 年 7 月 18 日” and the existing invented prop number. Screen text should have natural photographic softness rather than oversized sharp poster typography. The card should look like a photo of a physical card, not a full-screen app form.
No text saying “样卡”, “虚构”, “样例”, “SAMPLE”, or “DEMO”. No new headings, annotations, warning banners, arrows, red boxes, watermarks, official seal, government emblem, barcode or QR code.
```

### 再次局部微调

```text
Precise local image edit. Change only the rectangular ID-card photo inside the phone screen. Its current width-to-height ratio is about 1.4, still too tall. Make it a true normal landscape card with width-to-height ratio 1.59. Keep its WIDTH unchanged and decrease its HEIGHT by about 12 percent.

For the 1672×941 input image, aim for the card corner positions approximately:
top-left (649,347), top-right (1005,332), bottom-right (1019,558), bottom-left (658,574).
This makes the document roughly 357 pixels wide and 225 pixels high, with the existing phone-screen perspective.
The card top edge moves downward; the bottom edge stays approximately where it is. Fill the newly exposed strip above with the black phone-screen background.

Reflow the existing left-hand text fields and reduce the portrait size slightly to fit this shorter, correctly proportioned card. Preserve a normal portrait aspect ratio. Keep the current portrait and invented character details. Do not add a heading or label.
Everything outside the card remains unchanged: same phone, hand, fingers, desk, box, laptop, lighting, framing, overall 16:9 landscape image. No “样卡”, “虚构”, “样例”, SAMPLE, DEMO, captions, red annotation, arrows, watermark, official seal or scannable code.
```


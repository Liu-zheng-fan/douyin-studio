# 形象图导入：把白底角色图变成可用的透明 PNG

原始图通常来自生图工具，**白底、无透明通道、单张 3–4 MB**。
直接用会有三个问题：一块白底、边缘白边、体积太大。

这一步做三件事：**去背 → 去白边 → 缩到够用**。

## 方法

源图背景是纯白（实测角落 250–255），所以用**角落洪水填充**而不是全局阈值：

```python
从四个角落 floodfill(marker)  →  连通的背景被标记
标记处 alpha=0                →  只删背景，保留白米饭、白围裙
MinFilter(3) 腐蚀 1px          →  去掉贴边的白边
GaussianBlur(0.7)             →  轻微羽化，避免锯齿
缩放到 800×1066               →  竖屏 1080×1920 下角色占 56% 高，够用
```

**为什么不用全局阈值**：角色本身有大量白色（围裙、米饭、袜子），
按颜色删会把人物挖空。洪水填充只处理**连通的**背景。

## 完整脚本

```python
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

SENT = (255, 0, 255)          # 哨兵色：选一个画面里绝不会出现的颜色
SRC = Path(r"C:\Users\Root\Pictures\deepseek形象")
DST = Path("characters/xiaojingyu")

for p in sorted(SRC.iterdir()):
    if p.suffix.lower() not in (".png", ".jpg", ".jpeg"):
        continue
    im = Image.open(p).convert("RGB")
    w, h = im.size
    work = im.copy()
    d = ImageDraw.Draw(work)
    for xy in [(1, 1), (w - 2, 1), (1, h - 2), (w - 2, h - 2)]:
        ImageDraw.floodfill(work, xy, SENT, thresh=16)

    arr = np.asarray(work)
    mask = Image.fromarray(
        ((~np.all(arr == np.array(SENT, np.uint8), axis=2)) * 255).astype(np.uint8), "L")
    mask = mask.filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(0.7))

    out = im.convert("RGBA")
    out.putalpha(mask)
    out = out.resize((800, 1066), Image.LANCZOS)
    out.save(DST / (p.stem + ".png"), optimize=True)
```

19 张大约 76 秒，产出 18 MB。

## 检查结果

```bash
python -m douyin status        # characters.count 应该是 19
```

再出一帧看看边缘：

```python
from studio import character, shots, theme as th
p = character.pick("白饭")
img = shots.render(th.backdrop("dark"), {"type": "char", "_char_path": str(p),
                                         "text": ["今天有白饭"]}, 1.0, 3.0, {})
img.save("preview.png")
```

## 常见问题

| 现象 | 原因 | 处理 |
|---|---|---|
| 角色被挖空 | 背景不连通或阈值太高 | 降 `thresh` 到 8–10 |
| 边缘有白边 | 原图抗锯齿 | 加大腐蚀：`MinFilter(5)` |
| 背景残留光晕 | 背景是渐变不是纯色 | 换 `rembg` 一类模型，或手动抠 |
| 图片太大 | 没缩放 | 800×1066 已够竖屏用 |

## 换形象时

把新图丢进 `C:\Users\Root\Pictures\deepseek形象`，改两行路径重跑即可。
文件名就是动作名，不用改代码。

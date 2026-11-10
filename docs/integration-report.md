# 十个项目的融合报告

逐个读过源码，取走需要的，剩下的说明为什么不取。
「没取」不等于「不好」，多数是**和这条产线的形态不匹配**。

| # | 项目 | 取走了什么 | 落在哪 | 没取什么 | 为什么 |
|---|---|---|---|---|---|
| 1 | [bili-cli](https://github.com/kukemc/bili-cli) | Agent 友好 CLI 契约：单 JSON 输出、dry-run、稳定错误码 | 全部命令 | B 站接口本身 | 目标是抖音 |
| 2 | [EAC-design-world](https://github.com/Ebony-Vinyl/EAC-design-world) | 176 段 Shotcraft 真实镜头（broll 素材）；调色思路（对比/饱和/色温/lift） | `examples/` + `studio/theme.grade()` | 多轨时间线、曲线调色、剪映导出 | 插件形态（285MB、改宿主 GUI），与轻量产线冲突 |
| 3 | [fy-code-animation](https://github.com/Akillll-DuoHe/fy-code-animation) | ① motion-core 移植 ② 程序化背景（噪声/点阵/粒子/流场 + 文字区衰减）③ 逐字/波浪/弹入动效 ④ 转场（溶解/淡入淡出/擦除/推入/缩放） | `studio/motion.py` `fields.py` `typefx.py` `transitions.py` | 341 风格库的完整检索、Remotion 落地 | 风格库只做名字→处理映射（缺图时无法真复刻）；Remotion 在本机太重 |
| 4 | [douyin-script-pro](https://github.com/sheen945/douyin-script-pro) | HOOK-X 八钩子、300 分评分、万能句黑名单、金句检查 | `ops/gates.py` | 多模型接力（豆包/Gemini） | 只有 DeepSeek 一个模型可用 |
| 5 | [vibe-knowledge-film](https://github.com/HeyChengC/vibe-knowledge-film) | **音效引擎**：9 种事件音 + 卷积混响 + 低频铺底 + hush 静音门 | `studio/sfx.py`（去掉 scipy 依赖） | Canvas+Playwright 渲染引擎、两种画风 | 换引擎是架构级改动，先记在 P1；画风是知识类，与带货不符 |
| 6 | [dsh-video-pipeline](https://github.com/439436269-ctrl/dsh-video-pipeline) | 「核验通过才发布」的质量门思路；数据回写影响下一轮 | `studio/qc.py` + `ops/suggest.py` | 四平台发布、飞书回写 | 发布权限未拿到，平台侧不可控 |
| 7 | [dsh-directorx](https://github.com/LaplaceYoung/dsh-directorx) | — | — | 全部 | DSH 插件形态，能力与已实现部分重叠，引入会多一套依赖 |
| 8 | [guozhi-video-breakdown](https://github.com/GZ-L/guozhi-video-breakdown) | 爆款拉片十字段框架 | `ops/autopsy.py` + `docs/autopsy.md` | 自动化拆解 | 拆片子得人来看，机器只能记录与聚合 |
| 9 | [short-video-script-generator](https://github.com/leolx0623-art/short-video-script-generator) | — | — | 8 种结构模板 | 与已实现的六套骨架重复，且更粗 |
| 10 | [brewreel](https://github.com/Finderchangchang/brewreel) | — | — | 全部 | 50MB 工具集，DSH 集成部分与本项目定位重叠 |

## 量化结果

| 指标 | 融合前 | 融合后 |
|---|---|---|
| 测试用例 | 41 | **73** |
| 音频层数 | 1（人声） | **3**（人声 + BGM + 音效） |
| 音效事件 | 0 | 11 / 条 |
| 背景 | 纯色 | 4 种程序化动效（26–43ms/帧） |
| 文字动效 | 整块淡入 | 逐字 / 波浪 / 弹入 |
| 转场 | 硬切 | 5 种跨镜头转场 |
| 帧差 | 4.58 | **5.00** |
| 脚本评分 | 无 | 300 分制 + 硬门槛 |

## 一件必须说清楚的事

**帧差只从 4.58 到 5.00。** 加了音效、动态背景、逐字动效、转场、推近，指标几乎没动。

原因是这个指标测的是「像素变化量」，而六张静帧卡片的主体是**静止的大字**。
短剧、实拍、vlog 能到 30+，因为画面里一直有人和物在动。

所以结论是：**这条产线的天花板不在参数，在内容形态。**
要继续往上，只有两条路：

1. **换 Canvas/Playwright 引擎**（vibe 那套）——能把粒子、形变、3D 做起来，但仍是"图形"，不是"实拍"
2. **用真实素材**——录屏、实物、真人出镜

代码能保证的是「不出低级错误、每条都可复现、知道哪条有效」，保证不了「有人看」。

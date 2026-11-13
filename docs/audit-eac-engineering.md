# EAC-design-world vs douyin-studio：工程实现逐项对比

只比工程实现，不比创意。行号均为实际打开文件后读取到的位置（read 口径）。

## 0. 读过的文件与体量

| 项目 | 文件 | 行数 | 作用 |
|---|---|---|---|
| EAC | `src/media/grading.mjs` | 1025 | 调色参数表/校验/11 步转换/13 预设/.cube 生成 |
| EAC | `src/media/index.mjs` | 1312 | ffmpeg 滤镜链：inputLut→lut→参数调色→蒙版合成、预览、护栏、示波器、分批渲染 |
| EAC | `src/color-workflow.mjs` | 464 | .cube 严格解析、调色版本、曝光匹配建议、调色签名 |
| EAC | `src/export-nle.mjs` | 1916 | 剪映草稿 / FCP7 xmeml / SRT / LUT / bundle / zip |
| EAC | `src/engine.mjs` | 853 | 时间线数据结构与校验、修订历史、任务队列 |
| EAC | `vendor/video-shotcraft/catalog.json` | 9710 | 镜头配方索引（150 模板 / 124 配方 / 59 推荐） |
| EAC | `docs/grading.md` `nle-export.md` `architecture.md` | 82 / 109 / 75 | 参数与顺序、导出能力对照、渲染边界 |
| 我 | `studio/theme.py` | 258 | 画布/配色/断行/字幕/`grade()`/光带氛围 |
| 我 | `studio/render.py` | 163 | 时间线规划、逐帧渲染、manifest |
| 我 | `studio/pipeline.py` | 341 | 一条命令出片、ffmpeg 编码与混音 |
| 我 | `studio/ff.py` / `qc.py` | 81 / 174 | 定位 ffmpeg、成片质检 |

## A. 它有我没有

| # | 它能做 | 实现位置 | 我缺什么 |
|---|---|---|---|
| A1 | 参数调色烘焙成 `.cube`，渲染用 `lut3d` 套用 | `grading.mjs:769-909, 929-955`；`media/index.mjs:693-758` | 全项目无 LUT 概念；调色只有 `theme.py:205-229` 的像素运算，产物带不出去 |
| A2 | 外部 LUT 双段：`inputLut`（log→显示）→ `lut`（风格），并随工程复制 | `media/index.mjs:651-674`；`export-nle.mjs:1341-1372` | 无外部 LUT 字段，无复制/暂存机制 |
| A3 | HSL 分通道：`hueVsHue/hueVsSat/hueVsLum/lumVsSat` + 限定器二级调色（≤4 个） | `grading.mjs:29-40, 598-638, 680-742` | 只有全局 `saturation`（`theme.py:216-217`），不能只动蓝/绿，也不能按亮度查表 |
| A4 | 空间蒙版调色（circle/rect/linear + feather + opacity） | 校验 `media/index.mjs:488-520`；geq 蒙版 `579-603`；split/lut3d/maskedmerge `726-757` | `render.py:117` 只读顶层 `script["grade"]`，镜头对象不参与调色，没有任何局部调色字段 |
| A5 | 曲线（master/r/g/b，2–8 控制点，Fritsch–Carlson 单调插值） | `grading.mjs:255-278, 552-592, 880-887` | 无曲线；`ImageEnhance.Contrast` 的形状固定不可控 |
| A6 | 工程导出：剪映 `draft_content.json` + FCP7 xmeml + SRT + LUT + bundle + zip | `export-nle.mjs:17, 195-221, 444-620, 1007-1196, 1243-1327, 1503-1538` | 只写 `manifest.json`/`meta.json`（`render.py:131-151`、`pipeline.py:292-313`），人工续剪只能拿到 mp4 |
| A7 | 调色预览（前后对比表）+ 统计护栏 + 波形/矢量示波器 | `media/index.mjs:1032-1125, 1201-1260, 1283-1310` | `qc.py:52-91` 只看黑帧/0.4s 帧差/响度，没有任何色彩统计 |
| A8 | 调色版本 save/restore + 只含色彩状态的 sha256 签名 | `color-workflow.mjs:201-279, 453-464` | 无“版本”概念，manifest 不记录 grade，改一次就无从对比 |
| A9 | 镜头配方 JSON 目录（schemaVersion + stats + license/provenance） | `catalog.json:2-9`；索引与校验 `shotcraft-library.mjs:39-57, 90-124` | 17 个镜头是 Python 函数（`shots.py:70-806`，`SHOTS` 表 789-806），配方散在 `templates/script-skeletons.md`（55 行），机器不可检索 |

## B. 我有但更弱（量化）

| 维度 | 它 | 我 | 差距 |
|---|---|---|---|
| 参数数量 | 8 标量 + 9 通道值 + 3 分区×13 + 4 二级×21 = **约 140 个数值参数**，另有 13 个预设（`grading.mjs:4-40, 58-173`） | **4 个**（contrast / saturation / warmth / lift，`theme.py:208`） | ≈35 倍 |
| 处理链 | **11 步**：白平衡→曝光→lift/gamma/gain→offset→对比→曲线→饱和→自然饱和→色相→二级→钳制（`grading.mjs:744-768`，实现 `825-908`） | **3 步**：Contrast→Color→R/B 系数与整体加值（`theme.py:214-228`） | 11 vs 3 |
| 作用域 | 三层合并 `look → clip.grading → window.grading`（`grading.mjs:469-480`；`media/index.mjs:710, 737`） | 单层全局，作用于**合成后的整帧**（`render.py:116-118`），字卡和图片一起偏黄 | 无层级、无 per-shot |
| 数值精度 | gamma 空间浮点、全程 clamp、跑在解码位深（`grading.mjs:825-908`；`docs/grading.md:9`） | 8-bit 整数 `point()` + `int()` 截断（`theme.py:223-227`），暖调时暗部会断层 | 8-bit vs 10-bit |
| 可复用性 | 同一 transform 出 `.cube`，剪映/PR/Resolve/PS 通用（`docs/grading.md:80-82`） | 调色只存在于 PNG 像素里，出了 mp4 就消失 | 0 个宿主可用 |
| 时间线记录 | 项目含 `clips[].track/start/sourceIn/speed/motion/windows` + `history/revision`（`engine.mjs:657-745`） | manifest 只有 index/type/start/duration/text + 字幕（`render.py:131-151`） | 无法据此重建工程 |
| 质检维度 | 亮度/饱和/高光裁切/暗部死黑 + 前后对比（`media/index.mjs:1032-1125, 1201-1260`） | 黑帧占比、开场运动量、LUFS/峰值（`qc.py:52-91, 126-146`） | 我强在“交片后”，它强在“调色后” |
| 镜头库 | 150 模板 / 124 配方 / 157 个 tsx + 许可溯源 | 17 个函数 + 55 行骨架 md | 数量与结构化都差一档 |

## C. 不适用（附依据）

| 项 | 依据 | 为什么现在不适用 |
|---|---|---|
| 多轨时间线（`clip.track`） | 它的字段：`engine.mjs:657-705`、`media/index.mjs:614-648`；我的：`render.py:43-65`、`pipeline.py:173-182` | 我的每一镜时长由配音长度 + lead/tail 推出，是顺序时间轴；镜头内部的叠层已经由 `shots.py:7` 的 `fn(base, t, dur, spec, assets)` 在同帧里完成，不需要并行轨。接真实素材/画中画时才需重估 |
| 变速 `clip.speed` | 字幕按语音比例切分：`render.py:60-64`；时长来自 TTS：`pipeline.py:173-182` | 配音先于画面生成，变速会让口播与字幕错位，且要先变速音频；当前形态下没有安全实现 |
| 分区轮 `zones` | `grading.mjs:31-33, 646-677`；`docs/grading.md:31` | 它面向实拍 log 素材的连续影调；我的画面是固定品牌色的扁平合成（`theme.py:25-51`），没有可“救”的亮度分区。broll 也已在 `pipeline.py:93` 抽成 RGB 帧，源头已显示参考 |
| `inputLut`（相机 log 转换） | `media/index.mjs:651-663`；`docs/grading.md:44-49` | 我的素材是生成图/透明 PNG/已调色 stock 视频（`pipeline.py:56-94`），没有 log 源，接了也是空转 |
| 多 Pass 分批渲染 | 它 >10 片段才分批（`media/index.mjs:844-870`），原因写在 `docs/architecture.md:71`：几十个 4K 解码器同时驻留会 OOM | 我固定 1080×1920、≤60s、走 PNG 帧序列（`pipeline.py:242-260`），同一时刻只有编码器无解码器，这个问题不存在 |

## D. 最该抄的 5 条工程做法

1. **把调色编译成 `.cube`，在编码前用 `lut3d` 套用**（`grading.mjs:769-909, 929-955`；`media/index.mjs:693-758`）。
   预期：参数 4→约 140；调色代码只维护一份，预览/成片/导出共用同一 transform；省掉逐帧 PIL 全图 `point()`（1080×1920、每帧 2 次）。
2. **参数范围表 + 未知键拒绝 + 控制点校验**（`grading.mjs:4-20, 203-207, 255-278`）。
   预期：`script.json` 里写错的 grade 在 build 前报中文错误，和 `douyin/schema.py:58` 的字段说明对齐，不再静默降级成“没调色”。
3. **把调色护栏塞进 `qc.py`**（指标定义 `media/index.mjs:1201-1260`，统计采样 `1093-1105`）。
   预期：新增 lumaMin/lumaMax/饱和均值/高光裁切率 4 个指标，block 规则从“黑帧/静音/超长”扩到“调色后高光触顶、暗部死黑”。
4. **先出 SRT + LUT 交接包，不追剪映草稿**（SRT `export-nle.mjs:195-221`；LUT `1243-1327`；manifest `1503-1538`）。
   预期：一条命令产出 `captions.srt` + `look.cube` + handoff manifest，人工续剪从“只有 mp4”变成可用；绕开 1916 行里的 xmeml/草稿复杂度。
5. **镜头库改成数据，渲染函数保留**（`catalog.json:2-9`；校验与检索 `shotcraft-library.mjs:39-57, 90-96`）。
   预期：`shots.py` 的 17 个函数继续当渲染实现，配方抽成 JSON（type/energy/category/duration/params），schema、CLI、检索都能读，AI 选镜头有据可依。

结论：我的缺口集中在“色彩链路”和“交付格式”两层，不在渲染本身；A1–A6 都能在不改 `shots.py` 的前提下逐条补。

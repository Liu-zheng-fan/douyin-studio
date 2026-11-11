# 参考项目审计：我到底取了什么、漏了什么

写这份是因为被问了一句"你是不是也在省事"。
查完之后：**是，而且不止一处。** 下面是逐项交代。

判定分三类：
- ✅ 已全量采用
- ⚠️ 部分采用（说明为什么）
- ❌ 漏了（区分"能力缺口"和"我图省事"）

---

## 1. bili-cli（MIT）

| 它有什么 | 我取了什么 | 判定 |
|---|---|---|
| Agent 友好 CLI 契约 | 单 JSON 输出、dry-run、稳定错误码 | ✅ |
| B 站所有接口 | 未取（目标不是 B 站） | ⚠️ 形态不匹配 |
| 数据诊断（3秒退出/封面倍数） | 只借鉴了指标口径 | ⚠️ |

---

## 2. EAC design world（AGPL-3.0）

| 它有什么 | 我取了什么 | 判定 |
|---|---|---|
| 150 段 Shotcraft 镜头 | **全量 147 段 + 索引** | ✅（曾只取 8 段，已修） |
| 调色工作台（曲线/HSL/蒙版/LUT） | 只做了 contrast/saturation/warmth/lift 四个参数 | ❌ **能力缺口** |
| 多轨时间线 | 未取（我们是顺序时间轴） | ⚠️ 形态不匹配 |
| 剪映 / FCP7 导出 | 未取 | ❌ 缺口（人工续剪场景需要） |
| 150 个 Shotcraft 镜头配方（JSON） | 未取 | ❌ 漏了 |

---

## 3. fy-code-animation（AGPL-3.0）

| 它有什么 | 我取了什么 | 判定 |
|---|---|---|
| 341 条风格提示词 | **全量 535 个文件随项目走** | ✅（曾只做名字映射） |
| motion-core | 移植为 Python | ✅ |
| 程序化背景 | 移植 4 种（噪声/点阵/粒子/流场） | ✅ |
| 逐字动效 | 移植 3 种（type/wave/pop） | ✅ |
| 转场 | 自研 5 种（溶解/淡入/擦除/推入/缩放） | ✅ |
| 78 个 md 模块 | 只读了约 5 个 | ❌ **漏了** |
| 16 个 recipes | 只读了 2 个（meaning / narrative） | ❌ 漏了 |
| TSX 原始实现 | 复制到 `vendor/`，未移植 | ⚠️ 参考用 |
| 351 风格库的「复刻」能力 | 只做了关键词→处理映射 | ❌ 缺口 |

---

## 4. douyin-script-pro（0★）

| 它有什么 | 我取了什么 | 判定 |
|---|---|---|
| HOOK-X 八钩子 | 全 8 型 | ✅ |
| 300 分评分 | 自研 300 分（不同权重） | ⚠️ 等价替代 |
| 万能句黑名单 | 已实现 | ✅ |
| 六种故事结构 | 只有六套镜头骨架（不是同一回事） | ❌ 漏了 |
| 三道预检（复审生存/戏剧动作/潜台词） | 未实现 | ❌ 缺口 |
| 创意点火引擎（12 路发散） | 未实现 | ❌ 漏了 |
| MVP 72 小时冷启动协议 | 未实现 | ❌ 漏了 |

---

## 5. vibe-knowledge-film（1216★）

| 它有什么 | 我取了什么 | 判定 |
|---|---|---|
| 音效引擎 | **完整移植**（9 事件 + 混响 + 铺底） | ✅ |
| Canvas + Playwright 渲染 | **未移植** | ❌ **最大缺口** |
| 两套拆解画风（夜曲/寓言） | 未取 | ❌ 缺口 |
| `visualization.md`（282 行） | 未读 | ❌ 漏了 |
| `prompts.md`（283 行） | 未读 | ❌ 漏了 |
| 30 秒样片确认流程 | 未实现 | ❌ 漏了 |

---

## 6. dsh-video-pipeline（7★，19 skills）

| 它有什么 | 我取了什么 | 判定 |
|---|---|---|
| 读音校正 `pinyin_fix.py` | **刚移植**（同音替换 + 数字读法） | ✅（今天补的） |
| media-verify 质量门 | 自研 qc | ⚠️ 等价 |
| tangshi-data-review | 自研 suggest | ⚠️ 等价 |
| `douyin-publish`（41KB） | **没读** | ❌ **漏了** |
| `chinese-tts` 其余部分 | 只取了校正 | ⚠️ |
| `video-cover`（封面） | **没读** | ❌ 漏了 |
| 四平台发布 | 未取 | ⚠️ 需要权限 |

---

## 7. dsh-directorx（48★，640 个 md）

**从没打开过。** 判定：❌ **图省事**。

里面有：`video-prompt-builder`、`video-prompt-reverse`（视频提示词反推）、
`novel-characters`、`novel-art`、`minimax-h3-prompt-copilot`、`recipes/` 15 篇。
**这正是我 imggen 提示词最弱的一环。**

---

## 8. guozhi-video-breakdown（9★）

| 它有什么 | 我取了什么 | 判定 |
|---|---|---|
| 十字段拉片框架 | 全取 | ✅ |
| `evidence-extraction.md` | 没读 | ❌ 漏了 |
| `replication-output-template.md` | 没读 | ❌ 漏了 |
| `extract_video_evidence.sh` | 没读 | ❌ 漏了 |

---

## 9. short-video-script-generator（2★）

**从没打开过。** 判定：❌ 图省事，但影响小（8 种结构，已被自研六套骨架覆盖）。

---

## 10. brewreel（184★，177 个 md）

**从没打开过。** 判定：❌ **图省事**。

里面有：**19 个镜头规格**（每个带时长/字幕规则/参数速查）、`brief-template.md`、
18 个主题配色、28 个图标、行业模板（餐饮/教培/美业/travel）、`distill/`、`styles/`。
**这是最接近"我们该有的镜头库"的一份。**

---

## 总结：12 处漏取

| 类型 | 数量 | 例子 |
|---|---|---|
| **图省事**（没打开就判断） | 3 | directorx、brewreel、script-generator |
| **读了但没读全** | 5 | fy 的 78 个模块、vibe 的两份长文档、douyin-publish、video-cover、guozhi 的 3 个文件 |
| **真能力缺口**（要额外运行时/权限） | 4 | Canvas 引擎、调色工作台、NLE 导出、四平台发布 |

## 补课优先级

| 优先级 | 补什么 | 为什么 |
|---|---|---|
| P0 | brewreel 的镜头规格 | 直接扩我们的镜头库，且有参数上限 |
| P0 | directorx 的提示词工程 | 生图质量最弱的一环 |
| P1 | douyin-publish / video-cover | 发布与封面的实战细节 |
| P1 | douyin-script-pro 的三道预检 | 内容质量的硬闸门 |
| P2 | Canvas 引擎 | 要装 Chrome，工程量大 |
| P2 | 调色工作台 | 有真实素材后才值得做 |

## 一条教训

**"形态不匹配"和"我懒得看"是两回事，我当时混着用了。**
以后凡是写"不适用"，必须附一句"我读过 xx 文件，因为 yy 所以不取"。

---

## 补课进度（2026-11-11 更新）

| 项 | 状态 | 落点 |
|---|---|---|
| 读音校正（多音字同音替换） | ✅ | `studio/pronounce.py`，53 条规则 + 数字读法 |
| brewreel 镜头规格 | ✅ 部分 | 新增 `steps` / `meter` / `price` / `quote`，`number` 支持 from/prefix/showFrom |
| directorx 提示词工程 | ✅ 部分 | `studio/prompt.py`：六槽位 + 6 个画风预设 + 负面压制 |
| douyin-script-pro 三道预检 | ✅ | `ops/gates.py` 的 `precheck()`：复审生存 / 戏剧动作 / 潜台词 |
| video-cover 要点 | ✅ 部分 | 封面限两行、新增 `cover_pill` 高亮胶囊 |
| Canvas 引擎 | ❌ 未做 | 需 Chrome + Playwright |
| 调色工作台 / NLE 导出 | ❌ 未做 | 有真实素材后再做 |
| brewreel 其余 15 个镜头 | ⏳ 待做 | 需要真实截图/录屏的几类先放着 |

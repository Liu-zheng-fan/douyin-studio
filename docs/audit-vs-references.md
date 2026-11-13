# douyin-studio 工程对比审计（vs dsh-directorx / dsh-video-pipeline）

只比工程实现。行号均为实读。

## 0. 先定性：参考项目不是"纯文档"

| 项目 | 形态 | 证据 |
|---|---|---|
| dsh-directorx | **文档 + 可执行插件**：640 个 md / 55 个 skill 目录 / 365 个 knowledge 文件，另有 224 个 TS 源文件、44 个测试、15 个 recipes、6 个 workflows | `package.json` main=`lib/index.js`（1.8MB 构建产物）；`src/prompt-plan.ts`、`src/prompt-craft.ts` 是真代码 |
| dsh-video-pipeline | 纯脚本型 skill：37 个 md + 可执行 py/mjs | `media-verify/scripts/media_verify.py`、`chinese-tts/scripts/pinyin_fix.py` 均可直接跑 |

关键差别：directorx 把"提示词"做成了**带准入的闭环**（读凭据 → 成稿 → craftId → 生成），文档只是语料。我的项目把"提示词"做成了**字符串拼接函数**。

## A. 它有我没有

| 能力 | 参考实现（文件:行） | 我的现状 |
|---|---|---|
| 提示词 L1/L2/L3 分级 | `video-prompt-builder/references/levels.md:17/65/152` 三套骨架（6/12/23 模块）；且**代码里也判档** `src/prompt-plan.ts:59-64` 正则推断 L1/L2/L3 | `studio/prompt.py:58-78` 单档 6 槽位，无分级 |
| 六要素缺口清单 | `prompt-plan.ts:27-34,85-91,117-131` 逐要素 present/缺失 + 物理链 5 段 `:36-42`，回传 `agentPrompt` | 无。prompt.py 只有 `describe()` 自述 |
| 提示词反推 | `video-prompt-reverse/SKILL.md:85-181` 9 步；`references/templates.md:5-58` 还原版/增强版填空模板；`diagnosis-matrix.md` 6 维诊断；ffmpeg 抽帧 `SKILL.md:111-119` | 无任何反推路径 |
| 成稿硬闸（craftId） | `prompt-craft.ts:93-115` 未读 skill/knowledge 直接 refuse；`:66-78` isThinPrompt（<120 字/缺 5 维中 1 维即拒）；`research-ledger.ts:16` 读凭据 45 分钟过期；`tools.ts:412,465` 生成必须带 craftId | `ops/gates.py` 只打分，且 `pipeline.py:153` 默认不拦（见 B） |
| TTS 逐字裁决表 | `pinyin_fix.py:147-177` RISK 29 个字**每字一条具体裁决文案**；`:211-241` pinyin 模式用 pypinyin 异构体逐字标 ⚠，有风险 exit 1 | `studio/pronounce.py:101` RISK_CHARS 25 字压成一个字符串，`:180` 提示语统一一句话；**无 pinyin 模式** |
| TTS 规则可扩展 | `pinyin_fix.py:180-187` `--table extra.json` 追加 + 长词优先排序 | 无外部规则表 |
| 音频版本比对 | `media_verify.py:108-155` 成片 vs 参考 wav 的 NCC（粗 1280→细 16→微 1 三段找峰），0.9/0.3 双阈值判新旧版 | `studio/qc.py:129-133` 只测 LUFS/peak，**无法证明用的是新版配音** |
| 分窗音频对位 | `media_verify.py:82-99` 任意 `-w name:start:end` 多窗 RMS，配音窗 -18~-24dB / 静默 -inf | 无 |
| 双平台封面规格 | `video-cover/SKILL.md:31-35` 1146×717 + 1080×1920；`make_cover.py:62-77` 按 `w*717/1146` 算中心横裁带 | `studio/cover.py:89-92` 只有 1080×1440 与 9:16，无 16:10、无 1:1 |
| 封面平台侧回读校验 | `douyin-publish/SKILL.md:297-301` 平台回读 540×721，Pillow 中心窗滑扫 mad<12 判 MATCH | 无（封面只本地生成，不校验平台是否吃对） |
| 发布自动化 | `douyin-publish/SKILL.md:68-134` playwright 全流程；`:180-192` 11 条坑位；`:198` 300012 风控=必须 headed；`:232-253` 合集写接口；`:286-311` 已发布换封面 | `douyin/publish.py:145-166` 开放平台骨架 + `:88-110` 人工包；`docs/publish-playwright.md:4` 自认"没有实现自动发布" |
| 复盘指标 | `tangshi-data-review/SKILL.md:43-51` 6 维 + 1 实验；`:35` 龄期 5 档衰减；`:53-62` 8 节报告模板；`:13` T+6/24/48 三点采样 | `ops/review.py:23-47` 1 个分组变量 × 中位数 |

## B. 我有但更弱（量化）

| 维度 | 参考 | 我的 | 差距 |
|---|---|---|---|
| TTS 规则数 | 88 条（`pinyin_fix.py:20-144`）+ 29 条逐字裁决 | 53 条（`pronounce.py:19-98`）+ 25 字单句提示 | 规则 **-40%**；具体裁决 **29→0** |
| TTS 模式 | fix / check / pinyin 三模，check 有 exit 1（`:295`） | fix / check 两模，`check()` **全仓库无调用点**（audio.py:173 只调 fix） | 校验环节 **未接入流水线** |
| 质检项 | 3 原子件，其中 astats/NCC 可参数化任意窗 | 9 条 code，3 级 | 音频侧覆盖 **0/2**；且 `qc.py:135` 的字幕长度检查在 outbox.py:53 与 daily.py:132 都没传参 → **不可达** |
| 内容闸门强度 | 无 craftId 不能生成（硬） | 12 项 300 分（`gates.py:101-140`），`pipeline.py:153` 仅在 `force or strict_gates` 时才真拦 | 硬卡 **0 处**；且极性与 `:138-139`（force 放行合规）相反，疑似写反 |
| 复盘维度 | 6 维 + 衰减 + 平台权重 + 同龄期对照 | 1 维分组、median/mean/best/n | 分析维度 **6→1（-83%）**，平台 **3→1**，龄期归一 **0** |
| 封面规格 | 2 平台 + 中心裁切 + 回读比对 | 2 版，纯本地 | 规格 **-1 类**，校验 **0** |
| 发布坑位库 | 11 条 + 9 条合集坑 + 8 条换封面坑 | 0 条（仅 docs 里 4 条二手转述） | **0 vs 28** |

## C. 等价或更好

| 项 | 说明 |
|---|---|
| 质检分级 | `qc.py:7-10` block/warn/info 三级 + 数值阈值（黑帧 >25% block、`:125` 开场变化 <1.2、`:130` LUFS -17~-12、`:132` peak -1.0）；media-verify 只有 PASS/FAIL(exit 2) |
| 合规层 | `compliance.py:28-59` 4 类 76 词 + `:112-123` AI 标识硬阻断 —— 两个参考项目都没有广告法/站外导流这层 |
| 审批箱 | `outbox.py:30-37` 6 类拒绝标签（带修复建议）→ `:53-56` 质检不过不进队列 → `:69-87` review.json + 单页 HTML + decision.json；参考项目只有 CLI 输出 |
| 拉片聚合 | `autopsy.py:53-94` 切镜间隔/留存密度/hook·engine·cta 分布 + 样本 <6 不下结论；参考无对应物 |
| CLI 契约 | `publish.py:28-35` stdout 单 JSON、退出码、`--dry-run`（`:177`）；三项目里最一致 |
| 测试密度 | 15 个 pytest / 31 个 py 模块 = 0.48；directorx 44/224 = 0.20 |

## 5 条最该抄的（按性价比排序）

1. **给 prompt.py 加分级 + 缺口清单**（照 `levels.md` 三骨架 + `prompt-plan.ts:85-131`）。静帧从 6 槽扩到 3 档（6/12/20 模块），按意图正则判档，返回"缺哪几要素+每条怎么写"。→ 出图一次过率上升，换主体不换画风。
2. **抄 craftId 闭环**（`prompt-craft.ts:66-78,93-126` + `research-ledger.ts:16`）。任何出图必须带 craftId，成稿前必须有 stylelib/knowledge 读凭据（45 分钟过期），成稿存 `prompt-crafts.json`。→ 杜绝"一句话直接出图"，质量可追溯。
3. **把 TTS 校验接进 build 并升级成三模**（`pinyin_fix.py:211-241,147-177,180-187`）。加 pinyin 逐字异构体扫描 + 每字裁决文案 + `--table` 热插规则，`check` 有非 0 退出码，`audio.py:173` 前后各跑一次。→ 多音字错读在上传前被机器拦住，不靠人耳。
4. **加 media-verify 的 audio-ncc + 分窗 astats**（`media_verify.py:82-155`）。成片音频 vs TTS 源 wav NCC≥0.9 判同版；配音窗 -18~-24dB、静默窗 -inf。→ 唯一能机器证明"这条片子用的是新版配音"的检查，防错版上线。
5. **复盘加龄期折算 + 分档**（`SKILL.md:35,43-62`）。`播放/日 = 播放 ÷ 龄期h × 24`，decay 分 5 档，T+6/24/48 三点采样，报告固定 8 节。→ 不同龄期的片子可比，避免"新片数据低=内容差"的误判。

## 顺带发现的 3 个 bug（本次审计副产品）

1. `pipeline.py:153` 条件写反：`--force` 本应放行，实际**强制拦截**评分不足的脚本（与 `:138-139` 对 compliance 的处理相反）。
2. `studio/qc.py:135-136` 字幕长度检查不可达：两个调用点都没传 `subtitle_chars`。
3. `studio/pronounce.py:173-181` `check()` 是死代码：流水线只调 `fix()`，等于只有"改"没有"验"。

---
name: douyin-studio
description: 抖音竖屏短视频的完整生产线与运营手册：写 script.json → 逐帧渲染 1080x1920 成片 → 机器质检 → 生成审批箱 → 人工一键通过/拒绝 → 发布 → 实验台账 → 单变量复盘。含人设卡、六套镜头骨架、数据判读规则、故障决策树、成本与账号安全红线。融合 fy-code-animation 的分镜方法论、EAC design world 的镜头概念、bili-cli 的 Agent 友好 CLI 契约。用于「做一条抖音视频」「改这条片子的开头」「复盘上条为什么没人看完」「让 AI 每天自动运营这个账号」「帮我审今天这条」这类请求。不用于生成式画面以外的素材获取、真实拍摄和保证流量。
---

# 竖屏短视频工作室

给**抖音企业号（个体工商户蓝 V）**用的一条完整产线。目标不是「能出片」，是**每出一条都比上一条多知道一点**。

## 0. 先看这里：它能做什么

```
script.json  ──渲染──▶  1080x1920 mp4  ──合规──▶  发布包 / 接口
     ▲                                              │
     └──────── 台账 + 复盘 ◀── 48 小时后的数据 ◀─────┘
```

**确定性**是这套东西的地基：同样的 script.json，跑两次得到逐帧一致的成片。所以「改了开头」这件事才能被单独验证。

## 1. 三条铁律（违反就别发）

| 铁律 | 具体要求 | 为什么 |
|---|---|---|
| **0.5 秒法则** | 第 1 帧就必须有运动、强对比或人脸。禁止黑屏淡入、禁止「渐显标题」 | B 站实测：3 秒退出率 59%（同类中位 36%），一半人死在开场 |
| **15–45 秒** | 口播文案控制在 60–140 字 | 完播率是首要推荐权重，50 秒以上的新号内容基本必崩 |
| **每镜一个变化** | 禁止「一句话 + 图标 + 淡入」逐句贴卡 | 观众看的是关系变化，不是排版 |

第 3 条是 fy-code-animation 的核心判准。判断方法：**删掉动画，意思还一样吗？** 一样就说明这一镜没有表达，只是装饰。

## 2. 标准流程（七步，不许跳）

**① 定 brief（写进 script.json 之前）**
一条视频只讲**一个**变化。用一句话写完：「观众进来时以为 X，出去时知道 Y。」
如果这句话写不出来，先别做视频。

**② 写 script.json**
字段见第 3 节。口播（`say`）决定时长，画面（`text`）要更短——**屏幕上的字不能和口播一字不差**，否则观众在读书，不听你说话。

**③ 自检**
```bash
python scripts/selfcheck.py
```
字体 / ffmpeg / 中文 TTS / 示例脚本 / 输出目录，一次全查。

**④ 出片**
```bash
python -m studio.pipeline examples/script-01.json
```
产物在 `dist/<name>/`：`video.mp4`、`cover_3x4.png`、`manifest.json`、`meta.json`。

**⑤ 看三帧再往下走**
```bash
python -m studio.pipeline examples/script-01.json --keep-frames
```
打开 `dist/<name>/frames/` 看第 1 帧、中间帧、最后一帧。**渲染成功 ≠ 画面正确。** 空画面、文字出界、字幕压字，都只有肉眼能发现。

**⑥ 合规**
`pipeline` 会自动跑，有 `block` 项直接拒绝渲染（除非 `--force`）。别习惯性 `--force`。

**⑦ 发布 → 记台账 → 复盘**
```bash
python -m douyin.publish package dist/demo-01
python -m ops.ledger add --title "..." --plays 320 --completion 0.28 --hook-type 提问开场
python -m ops.review --by hook_type --metric completion_rate
```

## 3. script.json 规格

```jsonc
{
  "name": "demo-01",                // 产物目录名
  "title": "标题（≤30 字，前 12 字最关键）",
  "desc": "简介",
  "tags": ["AI", "创业日记"],
  "handle": "@账号名",
  "cover_title": "封面大字，换行用 \\n",
  "cover_kicker": "角标，如「第 1 天」",
  "ai_generated": true,             // 必须 true，抖音要求显式标识
  "fps": 30,
  "voice": "narrator",              // narrator/anchor/warm/lively/passion 或完整名
  "rate": "-4%",                    // 语速，略慢压住念稿感
  "pitch": "-2Hz",                  // 音高，略低增加可信度
  "bgm": "auto",                    // auto | none | calm/warm/tense/drive/quirky | 本地文件路径
  "shots": [ ... ]
}
```

### 声音：音色与配乐

**配音走 edge-tts**（微软 Edge 朗读的神经音色），不是 Windows SAPI。SAPI 的 Huihui 是拼接式老音色，一开口就掉完播率。断网时自动降级到 SAPI 并打印告警。

| 别名 | 完整名 | 听感 | 适合 |
|---|---|---|---|
| `narrator` | zh-CN-YunxiNeural | 年轻男声，对话感 | 第一人称自述（默认） |
| `anchor` | zh-CN-YunyangNeural | 播音腔，冷面 | 反差、正经讲荒诞事 |
| `warm` | zh-CN-XiaoxiaoNeural | 最自然的女声 | 生活、陪伴 |
| `lively` | zh-CN-XiaoyiNeural | 活泼 | 快节奏 |
| `passion` | zh-CN-YunjianNeural | 激昂 | 宣言、燃 |

换音色只改 `voice` 一个字段，**不要改代码**。

**BGM 默认自动生成**，不下载素材。原因：抖音曲库识别敏感（版权风险），而素材库的曲子压到 0.16 音量后只剩糊。合成出来的 pad + 低音 + 脉冲，只承担「不空」和「定情绪」。

判定逻辑（`studio/bgm.py`，可用 `python -m studio.bgm <script.json>` 查看打分）：

| 情绪 | BPM | 编排 | 触发条件 |
|---|---|---|---|
| `calm` | 70 | 只有 pad + 低音 | 语速慢、复盘/数据类 |
| `warm` | 78 | pad + 心跳 | 有 `reveal`、生活化用词 |
| `tense` | 96 | 小调 + 稳定脉冲 | 有 `number`/`split`/`line` |
| `drive` | 112 | 琶音推进 | 有 `cta`、语速快 |
| `quirky` | 100 | 大调轻琶音 | 自嘲信号 ≥2（零/不会/撑/白饭） |

打分 = 关键词命中（**每个情绪封顶 4 分**）+ 镜头结构 + 语速 + 自嘲信号；平局按 `drive > quirky > tense > warm > calm` 取。想指定就写 `"bgm": "warm"`，想关掉写 `"none"`。

### 素材从哪来

| 来源 | 位置 | 内容 |
|---|---|---|
| 风格库 | `C:/Users/Root/Documents/风格提示词` | 341 个风格 `.md` + 193 张示例图 |
| 镜头库 | EAC `vendor/video-shotcraft/media/` | **176 段 mp4 真实镜头** |
| 你给的图 | 任意路径 | 产品照、角色图（鲸鱼娘之类） |

**没有生图能力**：本机无 GPU、无 torch、无图像 API key，本环境也没法抓网图（Wikimedia 403、Openverse 超时）。所以「凭空生成一个角色」做不到——`art` 镜头必须喂一张现成的图。

**能做的是「改图」**：同一张图，用算法改成匹配的画风。

| 处理 | 对得上库里的画风 | 做法 |
|---|---|---|
| `halftone` | 美漫网点（K13） | 网格采样亮度画点 |
| `pop` | 波普（K14） | 色阶压缩 + 通道错位 |
| `ink` | 线稿 / 剪影 | 边缘检测，白线黑底 |
| `chalk` | 粉笔黑板（K10） | 黑板底 + 白色描边 |
| `duotone` | 双色调 / 丝网印 | 强调色渐变映射 |

写 `"style": "auto", "style_keyword": "美漫网点"`，管线会自动检索风格库、选中 `K13`、映射到 `halftone`。检索可单独跑：`python -m studio.stylelib 网点`。

`broll` 会自动把 16:9 素材抽帧并裁成 9:16；`art` 会加缓慢推进（Ken Burns）+ 柔边暗带，保证白字在任何背景上都读得清。

### 生图（可选，需要 Key）

配好火山方舟的 Seedream（即梦）Key 之后，`art` 镜头可以不写 `image`，只写 `prompt`：

```jsonc
{ "type": "art", "say": "...", "prompt": "扁平插画，鲸鱼少女端着不锈钢盆…",
  "gen_size": "720x1280", "style": "halftone", "text": ["鲸鱼娘端着一个盆"] }
```

- 生成后仍会套 `style`（`none` 表示原图），所以「生成 + 统一画风」是一条链。
- 同 prompt 命中本地缓存（`assets/gen/`），重跑不重复计费。
- 没配 Key 或请求失败时**退回占位框并告警**，不会中断渲染。
- 配置步骤见 `docs/imggen-setup.md`；自检：`python -m studio.imggen --check`。

### 镜头类型

| type | 语义操作 | 什么时候用 | 关键字段 |
|---|---|---|---|
| `hook` | 抛出一个缺口 | **永远是第一镜**，0.5 秒内完成 | `text` `sub` |
| `number` | 让差距被看见 | 数据、价格、对比基数 | `label` `value` `unit` `note` |
| `split` | 否定 A，肯定 B | 「不是…而是…」 | `a` `b` `tag` |
| `line` | 因果路径 | 解释「为什么」，必须有先后 | `a` `b` |
| `reveal` | 产品登场 | 揭晓实物 | `name` `image` `labels` |
| `bullets` | 并列要点 | 三条以内，多了就拆 | `title` `items` |
| `art` | 静图 + 运镜 + 压字 | 产品照、角色图、风格库示例、**AI 生成** | `image` 或 `prompt` `style` `text` |
| `broll` | 真实镜头做背景 | 素材库片段、录屏 | `video` `text` |
| `cta` | 收束 | 最后一镜 | `text` `sub` `user` |

每镜都要有 `say`（口播），没有 `say` 就用 `--silent` 跑（只用于看画面）。

**时长不是写死的**，由 TTS 语音长度自动决定：`镜头时长 = 语音 + 0.18s + 0.30s`。

## 4. 命令速查

| 目的 | 命令 |
|---|---|
| 环境自检 | `python scripts/selfcheck.py` |
| 出片 | `python -m studio.pipeline <script.json>` |
| 换音色出片 | `python -m studio.pipeline <script.json> --voice anchor` |
| 不配乐 | `python -m studio.pipeline <script.json> --no-bgm` |
| 看 BGM 判定依据 | `python -m studio.bgm <script.json>` |
| 只快看画面（无配音） | `python -m studio.pipeline <script.json> --silent --keep-frames` |
| 强制忽略合规 | `python -m studio.pipeline <script.json> --force`（**慎用**） |
| 生成发布包 | `python -m douyin.publish package dist/<name>` |
| 机器质检 | `python -m studio.qc dist/<name>/video.mp4` |
| 投递审批箱 | `python -m studio.outbox pack dist/<name>` |
| 打开审批页 | `python -m studio.outbox serve --port 8787` |
| 试接口发布 | `python -m douyin.publish api dist/<name> --dry-run` |
| 真发（需权限） | `python -m douyin.publish api dist/<name> --yes` |
| 记一条数据 | `python -m ops.ledger add --title "..." --plays 0` |
| 看全部台账 | `python -m ops.ledger list` |
| 单变量复盘 | `python -m ops.review --by hook_type --metric plays` |
| 数据模板 | `python -m douyin.stats template` |

## 5. 发布：默认走人工包

**为什么默认人工**：抖音开放平台的「视频发布」权限主要面向企业/机构申请，个人号基本拿不到；网页端有 `a_bogus` 一类签名，自动化会进风控。企业号虽然可申请，但**一条 AI 文案踩了广告法，罚的是营业执照主体**。

所以：

- `package` → 生成 `publish/` 目录（成片、封面、文案、话题、清单），人照着发，30 秒。
- `api` → 只有拿到 `client_key / client_secret / open_id` 且开通发布权限时才用。默认 dry-run，加 `--yes` 才真发。

企业号还有两件 B 站没有的能力，值得用起来：
- **私信接口**：可做自动回复、留资、线索收集（个人号要 1000 粉才有类似能力）
- **巨量千川**：几百块能买初始曝光，用来做封面/开头的 A/B，比等自然推荐快

## 5.5 每日闭环（运营层）

工具解决「能不能做出来」，这一节解决「每天做什么」。完整手册在
[references/operations.md](references/operations.md)，人设卡在 [references/persona.md](references/persona.md)，
六套镜头骨架在 [templates/script-skeletons.md](templates/script-skeletons.md)。

**一天的样子**：02:00 取数 → 02:05 定今天唯一要动的变量 → 02:10 选题 → 02:15 写脚本 →
02:25 生图 → 02:40 渲染 → 02:45 质检 → 07:00 投递 → **08:00 人审批** → 08:05 发布 → 22:00 入库。

**人只做两件事**：给方向、点按钮。审批就一屏：

```bash
python -m studio.outbox pack dist/<name>      # 质检不过不会进队列
python -m studio.outbox serve --port 8787     # 手机连同一 WiFi 打开
```

拒绝必须选一个理由标签（选题/文案/画面/太慢/音频/产品），标签直接决定次日改什么。
**连续两次同一标签 = 模板有病，改模板不是改这条片。**

**开工前先做**：`python -m studio.qc` 过得去、`python -m studio.imggen --check` 是 `ready`、
上一轮被拒的标签记牢——今天不许重复同一个毛病。

## 6. 实验协议（这是整套东西的重点）

**一次只动一个变量。** 同时改标题、封面、开头，数据涨了也不知道为什么涨。

可测变量：`hook_type`（开场类型）、`duration`（时长）、`cover_style`、`bgm`、`cta`、`format`（口播/无声/图文）。

节奏：
1. **前 3 条当基线**——结构不动，只换 `hook_type`（提问 / 数字 / 反常识 / 冲突）。
2. 每条发完 **48 小时**再录数据（早录会看到半成品曲线）。
3. `n < 6` 时不要下结论；`review` 会自己提示样本不足。
4. 组数控制在 2–3 个，多了看不出差异。

判读优先级：**完播率 → 2 秒跳出 → 播放量**。播放量是结果，前两个是原因。

## 7. 合规红线（`block` 会直接拦）

| 类别 | 例子 | 处理 |
|---|---|---|
| 绝对化用语 | 最好、第一、顶级、100%、永久 | 换成可验证的具体描述 |
| 功效宣称 | 治疗、抑菌、杀菌、增强免疫、食品级 | 无检测报告不能写 |
| 价格诱导 | 全网最低、最后一天、亏本清仓 | 需与实际一致并留档 |
| 站外导流 | 加微信、扫码加 | 抖音限流，改用平台组件 |

AI 标识是**强制**的：`ai_generated: true` + 发布时勾选「内容由 AI 生成」。漏标处罚更重。

词表在 `studio/compliance.py` 的 `ABSOLUTE / EFFICACY / PRICE / OFFSITE`，可以按行业补充。

## 8. 必须问人的三件事

1. **产品实拍素材**——没有真盆、真店、真打包，企业号做不出可信的带货内容。工具不生成实物。
2. **千川预算**——有预算就能买数据做 A/B；没有就接受冷启动靠运气。
3. **营业执照经营范围**——卖的东西必须在范围内，否则是超范围经营。

## 9. 它做不到什么

- **生成图像**：默认没有生图能力（本机无 GPU、无 key）。配好 `IMGGEN_API_KEY` 后，`art` 可以用 `prompt` 走即梦生成；没配就走占位框。
- **自动找网图**：本环境抓图被拦（Wikimedia 403、Openverse 超时）。素材要么在本地库，要么你给，要么用生图。
- **生成真实画面**：`reveal` 里没有产品图就是灰底占位框。
- **保证流量**：推荐机制不透明，同样内容差两小时结果能差十倍。
- **判断选题**：没有任何代码能替你决定「今天该拍什么」。
- **全自动发布**：技术上能做到一部分，但不建议——风控与合规责任在企业主体。

> 想真正「生图」，两条路：① 配一个图像 API（即梦/通义万相/SD 服务），在 `art` 前加一步生成；② 换一台有 GPU 的机器跑本地 SDXL/Flux。两条都不在这套东西的默认路径里。

## 10. 三个来源项目各贡献了什么

| 项目 | 拿走了什么 | 没拿走什么 |
|---|---|---|
| `fy-code-animation` | 语义分镜方法、镜头必须有变化的判准、`motion-core` 的确定性数学（已移植成 `studio/motion.py`） | 341 风格库（不随包分发，需自备路径）、Remotion 落地代码 |
| `EAC-design-world` | 镜头/时间线的组织概念、Shotcraft「镜头即资产」的思路 | 整个插件（285 MB、React + Vite、改 GUI），不进这条轻量产线 |
| `bili-cli` | Agent 友好的 CLI 契约：stdout 一个 JSON、`--dry-run`、稳定错误码、先预览再写 | B 站特定接口（不适用抖音） |

## 11. 交给下一个会话时，按这个顺序读

1. 本文件（尤其第 1、2、6 节）
2. `studio/shots.py` 里的七个镜头函数——决定画面能做成什么样
3. `examples/script-01.json`——照着改，不要从零写
4. `studio/compliance.py`——发布前必跑

**不要做的事**：不要为了「更好看」加动效而不加信息；不要把 10 个镜头塞进 30 秒；不要跳过看三帧那一步。

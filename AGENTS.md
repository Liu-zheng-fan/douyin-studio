# AGENTS.md

给接手这个仓库的 AI 看。**先读这一页，再动手。**

## 这是什么

一条抖音竖屏视频的本地生产线：一个 JSON → 1080×1920 成片 → 机器质检 → 人工审批 → 台账。

## 30 秒上手（按顺序敲这三条）

```bash
python -m douyin status      # 现在能不能干活、有没有待审、台账几条
python -m douyin doctor      # 环境对不对（字体/ffmpeg/TTS/生图）
python -m douyin schema      # script.json 有哪些字段
```

**不要跳过 `status`。** 它会告诉你今天该做什么。

## 日常三条命令

```bash
python -m douyin gates  examples/script-04.json   # 1. 先给脚本打分（<200 别渲染）
python -m douyin build  examples/script-04.json   # 2. 出片
python -m douyin pack   dist/demo-04-first        # 3. 投递审批箱
```

其它命令见 `python -m douyin --help`。

## 地图

| 目录 | 是什么 | 什么时候看 |
|---|---|---|
| `studio/` | 渲染引擎（镜头/音频/音效/背景/转场/质检） | 要改画面时 |
| `ops/` | 运营逻辑（闸门/拉片/台账/复盘/建议/每日编排） | 要改判断时 |
| `douyin/` | 发布与数据 + **统一 CLI** | 要发片时 |
| `docs/` | 为什么这样设计、架构、失败案例 | 想改结构前先读 |
| `references/` | 运营手册、选题钩子、素材选型 | 要写内容时 |
| `templates/` | 六套镜头骨架 | 写脚本时照抄 |
| `characters/` | **形象库**：`characters/<角色>/<动作>.png`（透明 PNG，文件名=动作） | 要换形象时 |
| `assets/broll/` | **素材库**：147 段真实镜头（92MB），`studio/broll.py` 可按关键词挑 | 要真实画面时 |
| `assets/stylelib/` | 341 条风格提示词（13.6MB，随项目走不用依赖外部路径） | 要指定画风时 |
| `vendor/` | 参考源码与文档：fy 的 TSX、brewreel 镜头规格、directorx 提示词工程、dsh 的 19 个 skill（本地参考，不参与运行） | 想移植某项能力时先来这里翻 |

## 状态在哪

| 状态 | 位置 |
|---|---|
| 今天跑没跑 | `ops/state/YYYY-MM-DD.json` |
| 待审队列 | `outbox/<日期>/decision.json`（`status: pending`） |
| 发布台账 | `ops/ledger.jsonl` |
| 拉片样本 | `ops/autopsy.jsonl` |
| 生图缓存 | `assets/gen/`（同提示词不重复计费） |

这些都在 `.gitignore` 里，不进版本库。

## 三个不要

1. **不要跳过 `gates` 直接 `build`**——渲染一条要 2 分钟加几毛钱，脚本不过关全是浪费。
2. **不要 `--force` 绕过质检**——`block` 项都是真实故障（黑帧/静音/超长），绕过等于发废片。
3. **不要自动发布**——发布权限要资质，且违规罚的是营业执照主体。

## 遇到问题

- 画面全黑 → 看 `references/cases.md` 案例 2
- 生图报 `ModelNotOpen` → 案例 4，先用必败请求区分鉴权和权限
- 配置读不出来 → 案例 5，Windows 的 JSON 要按 `utf-8-sig` 读
- 帧差上不去 → 案例 8，**这是内容形态问题，不是参数问题**

## 一条纪律

**一次只改一个变量。** 同时改开头、封面、时长，数据涨了也不知道是谁的功劳。
台账和 `review` 就是为这件事存在的。

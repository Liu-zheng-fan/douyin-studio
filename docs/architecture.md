# 架构

## 一次出片发生了什么

```
script.json
    │
    ▼
load_script ── 校验 shots、锁死竖屏尺寸
    │
    ▼
compliance.report ── 有 block → 直接退出（不渲染，不浪费算力）
    │
    ▼
audio.durations ── 逐句 TTS → 每句真实秒数
    │
    ▼
plan_timeline ── 镜头时长 = 语音时长 + 0.18 前导 + 0.30 尾巴
    │              同时生成字幕表（按标点切句，均匀分布在语音区间）
    ▼
_prepare_assets ── art 镜头：生图 / 裁切 / 风格化
    │               broll 镜头：视频抽帧缓存
    ▼
render_frames ── 每帧：背景 → 镜头绘制 → 氛围光带 → 字幕 → PNG
    │
    ▼
ffmpeg ── x264 crf20 + aac，混音走 loudnorm + amix + limiter
    │
    ▼
qc.inspect ── block 就进不了审批队列
    │
    ▼
outbox.pack ── 复制成片/封面/脚本 → review.html + decision.json
```

## 三条不变量

**1. 确定性。**
`motion.py` 里所有函数只依赖 `t` 和参数，不读时钟、不用随机数。同一个 `script.json` 跑两次，
逐帧一致。没有这条，A/B 测试就是自欺欺人——你没法确认差异是改动带来的还是渲染噪声。

**2. 时长由声音决定。**
不是先定 30 秒再塞台词，而是先合成语音、量出秒数、再决定每镜多长。
所以改一句台词，时间轴会自动重排，字幕也不会错位。

**3. 质检在人工之前。**
`block` 级的片子（黑帧、静音、尺寸错、超长）根本不进审批队列。
原因是人的注意力是最稀缺的资源：让人看到一条坏片，第二天他就不看了。

## 镜头模型

每个镜头绑定一种**语义操作**，而不是一种排版样式：

| 镜头 | 语义 | 关键实现 |
|---|---|---|
| `hook` | 抛缺口 | 弹簧砸入 + 强调条生长 |
| `number` | 让差距可见 | 缓动 count-up，值随时间插值 |
| `split` | 否定 A 肯定 B | 划线按文字实际宽度，不按画布宽度 |
| `line` | 因果 | 连线走完才点亮 B——先后关系不能省 |
| `reveal` | 揭晓 | 升起 + 高光扫过（裁剪在 alpha 内） |
| `art` | 静图叙事 | Ken Burns + 柔边暗带 + 压字 |
| `broll` | 真实镜头 | 抽帧缓存，按时间取帧 |
| `bullets` | 并列 | 竖线生长 + 错峰 |
| `cta` | 收束 | 慢推进 |

新增镜头的方法：在 `shots.py` 写一个 `fn(base, t, dur, spec, assets) -> Image`，
注册进 `SHOTS` 字典，并在 `tests/test_shots.py` 的 `SPECS` 里加一行——测试会自动验证它出帧且会动。

## 为什么用 Pillow 而不是浏览器渲染

**优势**：零依赖、逐帧可控、启动快、Windows 上不折腾 Chrome。

**代价**：帧差只有 4–6（实拍约 33）。粒子、形变、3D 变换这类效果做不了。

这是当前最大的技术债。替换路径：把 `render_frames` 换成 Canvas + Playwright 截图，
其余模块（时间轴、音频、质检、审批）完全不用动——因为它们只依赖「一串 PNG」。

## 数据流

```
ops/ledger.jsonl ──► review.py ──► 单变量中位数对比
       ▲                                │
       │                                ▼
       └──── 人工录入 ◄──── 抖音创作者中心（无公开 API）
```

抖音的完播率、2 秒跳出只在后台页面里，没有稳定接口。所以这条链路目前是**人工录入**，
`ops/ledger.py` 的字段就是为了「一次只动一个变量」设计的。

## 扩展点

| 想改什么 | 改哪 |
|---|---|
| 加镜头类型 | `studio/shots.py` + `tests/test_shots.py` |
| 换配音引擎 | `studio/audio.py` 的 `synthesize()`，接口不变 |
| 换配乐策略 | `studio/bgm.py` 的 `MOODS` / `LEXICON` |
| 加合规词 | `studio/compliance.py` 的 `ABSOLUTE` / `EFFICACY` |
| 换渲染器 | `studio/render.py` 的 `render_frames()` |
| 换发布通道 | `douyin/publish.py` |

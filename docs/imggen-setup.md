# 接入即梦（Seedream）文生图

代码已经写完并通过连通性测试：`ark.cn-beijing.volces.com` 从这台机器**直连可达**（返回 401，说明服务器在应答，只差 Key）。

剩下的三步只能你本人做，因为涉及账号、实名和付费。

## 一、拿 Key（约 5 分钟）

1. **注册 / 登录火山引擎** → https://console.volcengine.com
2. **实名认证**（个人或企业都可以；企业认证用你的个体工商户执照更顺）
3. 进入 **火山方舟（Ark）** → 左侧 **「模型广场」** → 搜索 `Seedream` 或 `即梦`
4. 开通 **`doubao-seedream-3-0-t2i`**（文生图）。开通时可能会让你先充值/领额度
5. 左侧 **「API Key 管理」** → **创建 API Key** → 复制（形如 `ark-xxxxxxxx`，只显示一次）

> 记下「模型 ID」的完整名字。如果和我代码里默认的 `doubao-seedream-3-0-t2i-250415` 不一致，用第 6 步的 `IMGGEN_MODEL` 覆盖。

## 二、配置（二选一）

**A. 环境变量（推荐，不进代码库）**

```powershell
setx IMGGEN_API_KEY "ark-你的key"
```

设完要**新开一个终端**才生效。如果模型 ID 不同，再加一条：

```powershell
setx IMGGEN_MODEL "doubao-seedream-3-0-t2i-xxxx"
```

**B. 配置文件**

`C:\Users\Root\.douyin-studio\config.json`：

```json
{
  "imggen": {
    "api_key": "ark-你的key",
    "model": "doubao-seedream-3-0-t2i-250415"
  }
}
```

明文保存，机器上别放共享目录。

## 三、验证

```bash
cd ~/.dsh/skills/douyin-studio
python -m studio.imggen --check          # 期望 ready: true
python -m studio.imggen "一只端着不锈钢盆的鲸鱼少女" --size 720x1280
```

第二条第应该返回一个本地 PNG 路径，落在 `assets/gen/`。

## 四、接进视频

`script.json` 的 `art` 镜头可以只写 `prompt`，不写 `image`：

```jsonc
{
  "type": "art",
  "say": "一只鲸鱼娘，端着我的第一个产品。",
  "prompt": "扁平插画风格，拟人化的鲸鱼少女……",
  "gen_size": "720x1280",
  "style": "halftone",     // 生成后再套风格，none 表示原图
  "text": ["鲸鱼娘端着一个盆"]
}
```

出片：

```bash
python -m studio.pipeline examples/script-03-gen.json
```

## 注意事项

| 项 | 说明 |
|---|---|
| **计费** | 按张计费，价格随活动变动，以控制台为准。同 prompt 会命中本地缓存，不重复花钱 |
| **水印** | 代码里 `watermark: false`。即梦免费额度生成的图可能仍带水印，商用前确认 |
| **审核** | 生成内容要过平台审核；人脸、品牌、文字容易出现畸形，出图后要人眼过一遍 |
| **标识** | 抖音要求 AI 生成内容显式标识。`ai_generated: true` + 发布时勾选，不能省 |
| **不要写死模型名** | 火山会换版本号，404 时去模型广场确认最新 ID |
| **失败降级** | 没有 Key 或请求失败时，`art` 会退回占位框并打印警告，不会中断渲染 |

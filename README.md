# Singer · 用你的声音唱

本地运行的 AI 翻唱工具：上传你的演唱素材，选择一首歌，生成以你的音色演唱的版本。

- 音频只在本机处理，不上传云端。
- 当前技术路线：**RVC v2**（Colab 训练音色模型 + 本地推理）。
- 当前进度：**M0 已完成**；M1 分离/混音、M4 素材切片/训练包/模型导入、手机录音页已完成，RVC 推理与任务队列开发中。

## 快速开始

要求：macOS（Apple Silicon）、`ffmpeg`、`uv`。首次安装约 1–2GB 依赖。

```bash
./scripts/setup.sh     # 安装 Python 3.11 与依赖（torch / demucs / fastapi）
./scripts/dev.sh       # 启动 http://127.0.0.1:8765
```

打开浏览器进入 `http://127.0.0.1:8765`：

1. **我的声音**：上传 10–15 分钟干净干声（最低 5 分钟），勾选授权确认；也可以点「手机录音」用网址录。不会唱可选「轻松 · 约 5 分钟」。
2. **准备训练**：自动切片、质检，下载训练包；按 [docs/TRAINING.md](docs/TRAINING.md) 在 Colab 训练。
3. **导入模型**：把训练产出的 `.pth` + `.index` 导入音色。
4. **歌曲**：上传带原唱的完整歌曲，自动转码为 44.1kHz WAV。
5. **生成翻唱**：待 RVC 推理接入后开放。

## 手机 / 远程录音

Singer 自带引导式录音页：打开链接 → 跟着提示唱 → 音频自动保存到本机并切片。

- **同一台 Mac**：主界面点「手机录音」，复制链接打开即可。
- **手机 / 其他设备**：浏览器要求 HTTPS 才能用麦克风。用 `cloudflared tunnel --url http://127.0.0.1:8765` 生成临时 HTTPS 地址，再打开 `/record?token=...`。
- 访问令牌保存在 `data/record_token.txt`，不要公开分享。
- 完整步骤、Tailscale 方案与排错见 **[docs/REMOTE_RECORDING.md](docs/REMOTE_RECORDING.md)**。

## 命令行验证（M1）

```bash
# 分离人声 / 伴奏（输出到歌曲目录的 stems/）
.venv/bin/python -m app.pipeline.cli separate data/songs/<歌曲ID>/source.wav

# 混合并导出 WAV + MP3
.venv/bin/python -m app.pipeline.cli mix \
  data/songs/<歌曲ID>/stems/htdemucs_ft/source/vocals.wav \
  data/songs/<歌曲ID>/stems/htdemucs_ft/source/no_vocals.wav \
  data/songs/<歌曲ID>/outputs/mix.wav
```

- 默认使用 Apple Silicon 的 MPS；失败会自动回退 CPU。
- Demucs 权重首次运行下载到 `.cache/torch`，不会写入用户主目录。
- 实测：8 秒测试音频 MPS 分离约 45 秒；整首歌预计数分钟。

## 训练自己的音色

RVC 训练需要 NVIDIA GPU，本机只做推理。完整步骤（录制要求、Colab 参数、模型导入、排错）见 **[docs/TRAINING.md](docs/TRAINING.md)**。

简要流程：

1. 录 10–15 分钟干净清唱（最低 5 分钟；内容见 [docs/RECORDING.md](docs/RECORDING.md)）→ 上传到「我的声音」。
2. 「准备训练」→ 切片质检 →「下载训练包」。
3. 在 [Applio Colab](https://colab.research.google.com/github/iahispano/applio/blob/main/assets/Applio_NoUI.ipynb) 用 T4 训练（约 1–2 小时）。
4. 导出 `.pth` + `.index` → 在音色卡片「导入模型」。

## 目录结构

```
app/
  main.py          FastAPI 入口
  config.py        路径与端口配置
  audio.py         ffmpeg 探测/转码
  storage.py       data/ 下的目录与 JSON 元数据
  routers/         voices、songs、recordings API
  pipeline/        分离、混音、训练素材切片
  static/          主界面 + 手机录音页
docs/              训练、录音、远程录音文档
scripts/
  setup.sh         创建环境
  dev.sh           启动开发服务
data/              运行后生成：voices / songs / jobs（不入库）
models/            RVC 模型与索引（不入库）
WORKLOG.md         每次文件变更记录
MUSTDO.md          硬约束与里程碑
```

## 技术路线

| 阶段 | 内容 | 状态 |
|---|---|---|
| M0 | 脚手架、素材上传、转码、音色/歌曲管理 | ✅ 已完成 |
| M1 | Demucs 人声分离 + 混音导出（CLI） | 🚧 分离/混音已跑通 |
| M2 | RVC 本地推理（Apple Silicon MLX / MPS） | ⬜ |
| M3 | Web UI：任务进度、试听、下载 | ⬜ |
| M4 | 训练素材切片 + Colab 训练包 + 模型导入 | 🚧 切片/导入已完成 |
| M5 | 变调、降噪、失败重试、文档 | ⬜ |

> RVC 训练需要 NVIDIA GPU，本机只做推理；训练在 Colab 完成，模型文件（`.pth` + `.index`）下载后导入。推理候选方案：[RVC-MLX](https://github.com/Acelogic/Retrieval-based-Voice-Conversion-MLX)（Apple Silicon 专用，第三方实现，需验证）。

## 音频规格

- 统一 44.1kHz；歌曲双声道，训练素材单声道。
- 训练素材：无伴奏、无混响、无爆音，单人，建议 10–15 分钟（最低 5 分钟）。
- 成品：WAV 16bit + MP3 320k，响度约 -14 LUFS，峰值 ≤ -1 dBTP。

## 合规

- 仅允许本人或已获明确授权的声音；界面已加授权勾选。
- 生成内容应标注“AI 生成 / 声音转换”，不得用于冒充、诈骗、诽谤。
- 歌曲版权由使用者负责；本项目不内置曲库。

## 文档

- [WORKLOG.md](WORKLOG.md)：按时间记录所有文件变更。
- [MUSTDO.md](MUSTDO.md)：必须遵守的规则与必须完成的里程碑。
- [docs/TRAINING.md](docs/TRAINING.md)：录制、Colab 训练、模型导入与排错。
- [docs/RECORDING.md](docs/RECORDING.md)：录什么声音、10 分钟模板、绝对不要做的事。
- [docs/RECORDING_PROMPTS.md](docs/RECORDING_PROMPTS.md)：引导录音的逐条提示语与语音教练提示词。
- [docs/REMOTE_RECORDING.md](docs/REMOTE_RECORDING.md)：用网址在手机录音、HTTPS 隧道与安全注意事项。

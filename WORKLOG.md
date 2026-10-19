# 工作日志（WORKLOG）

> 规则：**每次新增 / 修改 / 删除文件，都要立刻在下面追加一条记录**。
> 只追加、不改写历史；如果记录有误，追加一条“更正”说明。
> 时间统一使用本机时区（Asia/Shanghai，CST）。

记录格式：

```
### HH:MM 标题
- 操作：新增 / 修改 / 删除
- 文件：`path/to/file`
- 说明：做了什么、为什么、结果如何
```

---

## 2026-10-19

### 17:08 初始化项目协作文档
- 操作：新增
- 文件：`WORKLOG.md`、`MUSTDO.md`、`.gitignore`
- 说明：
  - 建立本工作日志，作为后续所有文件变更的唯一记录入口。
  - 建立 `MUSTDO.md`，记录项目必须遵守的规则与必须完成的里程碑。
  - 建立 `.gitignore`，排除虚拟环境、模型权重、音频素材、输出文件、密钥等，避免误传 GitHub。
  - 已确认：本地仓库 `main` 分支尚无提交，远程 `origin` 指向 `https://github.com/EuphoriaTzbbaby/singer.git` 且当前为空。

### 17:08 技术路线确认（来自用户选择）
- 操作：决策记录（无文件变更）
- 说明：
  - 转换路线：RVC（Colab 训练 + 本地 MLX 推理）。
  - 歌曲类型：带原唱人声的完整歌曲，自动分离人声/伴奏后做音色转换。
  - 工具形态：本地网页应用（FastAPI + 静态前端）。

### 17:09 首次提交完成，推送失败（待配置 GitHub 凭据）
- 操作：Git 提交 / 推送
- 文件：`WORKLOG.md`、`MUSTDO.md`、`.gitignore`
- 说明：
  - 本地提交成功：`5761f7d chore: 初始化工作日志、必做清单与 gitignore`（3 files, +152）。
  - `git push -u origin main` 失败：`could not read Username for 'https://github.com': terminal prompts disabled`。
  - 排查结果：`gh` 未安装；keychain 中无 GitHub 凭据；`~/.ssh/id_ed25519` 存在，但 `ssh -T git@github.com` 返回 `Permission denied (publickey)`，说明该公钥未注册到 GitHub 账户。
  - 处理：保留本地提交，待用户添加 SSH 公钥或配置 PAT 后重试；后续达到里程碑会继续自动提交并推送。

### 17:11 创建 Python 3.11 环境与依赖清单
- 操作：新增 / 修改
- 文件：`pyproject.toml`、`.python-version`、`.gitignore`
- 说明：
  - 用 uv 安装 CPython 3.11.16 到项目内 `.python/`，创建 `.venv/`，避免污染系统 Python 3.14。
  - 依赖：fastapi、uvicorn、python-multipart、pydantic-settings、soundfile、numpy<2；音频额外依赖 torch、torchaudio、demucs、librosa、pyloudnorm、scipy。
  - `uv sync --extra audio` 成功：torch 2.14.1（MPS 可用）、torchaudio 2.11.0、demucs 4.1.0、numpy 1.26.4。
  - `.gitignore` 增加 `.cache/`、`.python/`（uv 缓存与解释器不入库）。

### 17:12 后端骨架与上传接口
- 操作：新增
- 文件：`app/__init__.py`、`app/config.py`、`app/storage.py`、`app/audio.py`、`app/main.py`、`app/routers/__init__.py`、`app/routers/voices.py`、`app/routers/songs.py`
- 说明：
  - FastAPI 入口 + `/api/health` + 静态页面挂载；启动时自动创建 `data/voices`、`data/songs`、`data/jobs`、`models`。
  - 音色：多文件上传（wav/mp3/flac/m4a/aac/ogg/opus）、强制授权勾选、转 44.1kHz 单声道 WAV、统计总时长、低于 1 分钟拒绝训练并提示、低于 10 分钟给警告。
  - 歌曲：上传后转 44.1kHz 双声道 `source.wav`，保存标题/歌手/时长。
  - 元数据统一写入 `meta.json`；删除接口校验路径必须在 `data/` 内。

### 17:12 前端界面
- 操作：新增
- 文件：`app/static/index.html`、`app/static/style.css`、`app/static/app.js`
- 说明：三步式深色界面（上传声音、上传歌曲、生成翻唱），含健康状态、列表、删除确认、上传中状态与 toast；生成按钮暂时禁用，等待 RVC 推理接入。

### 17:13 启动脚本与接口实测
- 操作：新增 / 修改
- 文件：`scripts/setup.sh`、`scripts/dev.sh`、`README.md`、`app/routers/songs.py`
- 说明：
  - 服务在 `http://127.0.0.1:8765` 启动成功；`/api/health`、首页、CSS/JS 均返回 200。
  - 用 ffmpeg 生成测试音频，实测音色上传（6 秒，返回“素材不足 1 分钟”警告）与歌曲上传（8 秒）成功。
  - 修复：歌曲原始文件与转码输出都叫 `source.wav` 导致覆盖报错，原始文件改存 `original/upload.<ext>`，复测通过。
  - README 补充环境、目录、技术路线、音频规格与合规说明。

### 17:14 切换 SSH 并首次推送成功
- 操作：Git 配置 / 推送
- 文件：无（远程地址变更）
- 说明：
  - 用户将 SSH 公钥添加到 GitHub 后，`ssh -T git@github.com` 认证通过。
  - `origin` 由 HTTPS 改为 `git@github.com:EuphoriaTzbbaby/singer.git`。
  - 首次推送成功：`5761f7d`、`4d6ecb3` 已上传，`main` 已建立跟踪。

### 17:14 更新里程碑状态
- 操作：修改
- 文件：`MUSTDO.md`、`README.md`
- 说明：M0（脚手架 + 素材上传/转码）标记完成；M1 人声分离待开始。

### 17:16 人声分离与混音模块
- 操作：新增 / 修改
- 文件：`app/pipeline/__init__.py`、`app/pipeline/separate.py`、`app/pipeline/mix.py`、`app/pipeline/cli.py`、`app/config.py`
- 说明：
  - 新增 Demucs 分离封装：默认 `htdemucs_ft`、双轨输出（vocals / no_vocals）；Apple Silicon 优先 MPS，失败自动回退 CPU；模型缓存固定到 `.cache/torch`，避免写用户主目录被系统拒绝。
  - 新增混音模块：两轨增益、LUFS 归一化到 -14、峰值限制 -1 dBFS、输出 16bit WAV + MP3 320k。
  - 新增命令行：`separate`、`mix`、`demo`，方便在接入 Web 任务队列前先验证整条链路。
  - 配置新增 `cache_dir`、`torch_home`、`demucs_model`、`demucs_device`，启动时创建缓存目录。

### 17:17 流水线实测与测试数据清理
- 操作：测试 / 删除
- 文件：`data/` 下测试数据（未入库）
- 说明：
  - 用 8 秒测试音频跑通：MPS 分离耗时 44.5 秒，生成 `vocals.wav` / `no_vocals.wav`；混音输出 8.0 秒 WAV 与 MP3，峰值 0.2219。
  - 对比测试：同一段音频 CPU 约 47 秒、MPS 约 13 秒（直接调用 demucs 时），确认 MPS 可用。
  - 通过 API 删除测试音色与歌曲，`data/` 已清空；同时验证 DELETE 接口正常。

### 17:18 更新 README（M1 用法与状态）
- 操作：修改
- 文件：`README.md`
- 说明：补充命令行分离/混音示例与实测耗时；进度表 M1 标记为“分离/混音已跑通”，等待 RVC 转换接入。

### 17:19 调研 RVC 本地推理方案
- 操作：调研（仅克隆到 `.cache/`，未入库）
- 文件：`.cache/deps/rvc-mlx/`（gitignore 已覆盖）
- 说明：
  - 浅克隆 [RVC-MLX](https://github.com/Acelogic/Retrieval-based-Voice-Conversion-MLX)（12MB），确认其纯 MLX 推理入口为 `rvc-mlx-cli.py infer`。
  - 它不能直接吃 RVC 的 `.pth`：需先用 `tools/convert_rvc_model.py` 转成 `.npz`，另需 `hubert_mlx.npz` 与 RMVPE 权重，并准备同名 `config.json` 指定 40k/48k 参数。
  - 仓库依赖固定 `torch==2.4.0`、`faiss-cpu==1.7.4`、`numba==0.60.0`，与主环境 torch 2.14.1 冲突，后续应建独立子环境，避免污染 Demucs 环境。
  - 尚未实际跑通推理：缺少可用的 RVC 模型（.pth + .index），等用户提供模型或完成一次 Colab 训练后验证。

### 17:50 训练素材切片、质检与训练包
- 操作：新增
- 文件：`app/pipeline/dataset.py`
- 说明：
  - 新增能量/静音切片：`librosa.effects.split` 找语音区间，合并短间隙、在低能量点拆分长段，目标 3–10 秒。
  - 每段做 -18 LUFS 响度归一化、峰值限制 -1 dBFS、10ms 淡入淡出，写 44.1kHz 单声道 16bit WAV。
  - 质检报告包含源时长、切片数、总时长、最短/最长/平均、削波比例、静音比例和警告。
  - 自动打包 `training_pack.zip`，内含 `dataset/*.wav`、`report.json`、`README.txt`。

### 17:51 音色接口：追加素材、准备训练、训练包、模型导入
- 操作：修改
- 文件：`app/routers/voices.py`
- 说明：
  - 新增 `POST /api/voices/{id}/files`：分批追加素材，自动续编号，失败只清理本次文件。
  - 新增 `POST /api/voices/{id}/prepare`：同步执行切片（后续迁入任务队列），写入 `dataset_report`。
  - 新增 `GET /api/voices/{id}/training-pack`：下载 zip，文件名带音色名。
  - 新增 `POST /api/voices/{id}/model`：导入 `.pth` + 可选 `.index`，校验扩展名与 PyTorch 文件头；同时提供 DELETE 重置。
  - 素材变化会作废旧切片与训练包；所有 `{voice_id}` 路径加正则校验，防止路径穿越。
  - 清理测试：非法 `.pth` 返回 400，路径穿越返回 404。

### 17:52 前端训练操作
- 操作：修改
- 文件：`app/static/index.html`、`app/static/style.css`、`app/static/app.js`
- 说明：
  - 音色卡片增加「添加素材 / 准备训练 / 下载训练包 / 导入模型」操作，支持隐藏文件选择器与按钮忙碌状态。
  - 列表展示已切片段数；训练包生成后才出现下载入口。
  - 追加素材或重新上传后提示需要重新准备训练。

### 17:53 训练流程实测
- 操作：测试 / 删除
- 文件：`data/` 下测试数据（未入库）
- 说明：
  - 用 84 秒合成音频测试：切片 12 段、总长 73.7 秒、平均 6.14 秒、静音占比 13.6%、训练包 70KB。
  - 追加同一文件后总时长 168 秒，旧训练包返回 404；重新切片得到 24 段、147.4 秒。
  - 用 zip 伪造 `.pth` 通过文件头校验并成功标记“模型就绪”；确认这只是导入链路测试，尚未做真实推理。
  - 删除测试音色，`data/` 已清空，服务日志无异常。

### 17:54 训练文档
- 操作：新增 / 修改
- 文件：`docs/TRAINING.md`、`README.md`
- 说明：
  - 新增完整训练指南：录制规范、切片报告解读、Applio Colab 参数（48k、Skip 切片、rmvpe、contentvec、300 epochs、batch 8）、导出与导入、常见问题、合规提醒。
  - README 更新进度、训练流程入口、目录结构与文档索引。

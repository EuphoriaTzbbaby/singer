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

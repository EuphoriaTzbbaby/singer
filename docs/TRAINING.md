# RVC 训练与模型导入

这份文档覆盖从“录声音”到“在 Singer 里导入模型”的完整流程。推理部分随 M2 接入，导入后的模型会显示为“模型就绪”。

> 具体录什么、录多久、怎么发声，见 **[RECORDING.md](RECORDING.md)**。

---

## 0. 录训练素材（决定上限）

RVC 是“学你的音色”，素材质量比算法更关键。

### 硬性要求

| 项目 | 要求 |
|---|---|
| 时长 | 10–15 分钟有效人声最佳，最低 5 分钟（少于 5 分钟效果明显下降） |
| 内容 | 演唱，不要说话；音域覆盖你常唱的歌 |
| 环境 | 安静房间，关闭空调/风扇，避免卫生间等强混响 |
| 设备 | 手机/耳机麦/电容麦均可，距离 15–25cm，避免喷麦 |
| 电平 | 峰值约 -12 到 -6 dBFS，**不能削波**（波形不能贴顶） |
| 格式 | WAV / M4A / MP3 都行，工具会统一转 44.1kHz 单声道 |
| 处理 | 关闭“降噪、混响、自动增益、美声/变声”等效果 |

### 怎么唱

- 分段录：每次 5–10 分钟，休息一下再录，避免疲劳走音。
- 曲目多样：慢歌、快歌、低音、高音都来一点，但都要在你能稳定唱好的范围。
- 每段开头留 1 秒安静，结尾也留 1 秒，方便切片。
- 不要清嗓、咳嗽、说话、跟唱伴奏（会混入伴奏）。
- 最好清唱；如果必须跟伴奏，请戴耳机，确保录音里**只有你的人声**。

### 常见废片

- 房间混响重 → 听起来“空”，模型会学到混响。
- 音量忽大忽小 → 切片响度不一致。
- 喷麦/爆音 → 产生噪声。
- 只有小声哼唱 → 缺少正常发声的动态。

---

## 1. 在 Singer 里准备训练包

1. 打开 http://127.0.0.1:8765
2. 「我的声音」上传素材（可多选、可分多次“添加素材”），勾选授权。
3. 点「准备训练」：自动切片到 3–10 秒、统一响度、统计质检指标。
4. 点「下载训练包」，得到 `你的音色名_rvc_dataset.zip`。

训练包内容：

```
dataset/slice_0001.wav ...
report.json      # 切片数量、总时长、静音比例、削波比例、警告
README.txt
```

如果报告提示“素材不足 10 分钟”“切片少于 50 段”，先补录再训练。

---

## 2. 在 Colab 训练

使用 Applio 官方 NoUI notebook（免费 T4 即可）：

**https://colab.research.google.com/github/iahispano/applio/blob/main/assets/Applio_NoUI.ipynb**

### 2.1 准备

1. 打开 notebook，菜单「代码执行程序 → 更改运行时类型 → T4 GPU」。
2. 按顺序运行前两个单元格：安装环境、挂载 Google Drive。
3. 把训练包上传到 Drive，例如 `/content/drive/MyDrive/singer/myvoice.zip`。
4. 在 Colab 里解压：

```bash
!unzip -o /content/drive/MyDrive/singer/myvoice.zip -d /content/drive/MyDrive/singer/myvoice
```

解压后应看到 `/content/drive/MyDrive/singer/myvoice/dataset/*.wav`。

### 2.2 参数

在 “Setup model parameters” 单元格：

| 参数 | 建议值 |
|---|---|
| `model_name` | `myvoice`（英文/数字，后面导入时用不到名字） |
| `sample_rate` | `48k` |

在 “Preprocess Dataset” 单元格：

| 参数 | 建议值 | 说明 |
|---|---|---|
| `dataset_path` | `/content/drive/MyDrive/singer/myvoice/dataset` | 指向切片目录 |
| `cut_preprocess` | `Skip` | 我们已经切好，避免二次切片 |
| `normalization_mode` | `none` | 切片时已做响度统一 |

在 “Extract Features” 单元格：

| 参数 | 建议值 |
|---|---|
| `f0_method` | `rmvpe` |
| `embedder_model` | `contentvec`（中文歌也可先用它；有 `chinese-hubert-base` 可试） |
| `include_mutes` | `2` |

索引：`index_algorithm` 选 `Auto`。

在 “Start Training” 单元格：

| 参数 | 建议值 |
|---|---|
| `total_epoch` | `300`（首次可 200，追求质量 400–500） |
| `batch_size` | `8`（T4 显存不够降到 4） |
| `pretrained` | `True` |
| `save_every_epoch` | `10` |
| `save_only_latest` | `True` |
| `save_every_weights` | `True`（方便拿最终权重） |

T4 上 10–15 分钟素材、300 epochs 大约 1–1.5 小时。中途断开可以从最新 checkpoint 继续。

### 2.3 导出

运行 “Export model”，`export_for` 选 `inference`。会在 Drive 的 `ApplioExported/` 下生成 `myvoice.zip`，里面有：

```
myvoice/myvoice_...e_...s.pth   # 模型权重
myvoice/myvoice.index            # 检索索引
```

---

## 3. 导入 Singer

1. 解压导出的 zip。
2. 回到 Singer，在对应音色卡片点「导入模型」。
3. 同时选中 `.pth` 和 `.index`（索引可选，但强烈建议带上）。
4. 卡片变为「模型就绪」，即可等待 M2 推理接入后生成翻唱。

> 模型文件保存在 `data/voices/<id>/model/`，不进 Git。
> 换模型：再次点「导入模型」覆盖即可。

---

## 4. 常见问题

| 现象 | 原因 / 处理 |
|---|---|
| 训练报 CUDA OOM | `batch_size` 降到 4 或 2；关闭 `cache_data_in_gpu` |
| 训练 loss 不降 | 检查素材是否有伴奏/混响；epoch 加到 500；换 `contentvec` |
| 导出没有 `.index` | 索引步骤没跑或失败；重跑 “Generate index file” |
| 导入提示“不是有效的 RVC 模型” | 选错了文件；必须是训练产出的 `.pth`，不是 zip |
| 相似度低 | 素材太少/太杂；音域不匹配；尝试 48k + 更多干净素材 |
| 中文咬字怪 | 换 `chinese-hubert-base` 重新提取特征并训练 |

---

## 5. 合规提醒

- 只训练**本人**或已获明确授权的声音。
- 训练歌手的翻唱素材仅限个人使用；公开发布需处理词曲版权。
- 生成内容请标注“AI 生成 / 声音转换”。

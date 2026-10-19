const TOKEN = new URLSearchParams(location.search).get("token") || "";

const STANDARD_STEPS = [
  { stage: "准备", text: "站好，深呼吸，准备开始", seconds: 3 },
  { stage: "元音", text: "用舒服的中音唱「啊」，保持 5 秒", seconds: 6 },
  { stage: "元音", text: "再唱一次「啊」，音量保持平稳", seconds: 6 },
  { stage: "元音", text: "高一点唱「啊」，不要挤", seconds: 6 },
  { stage: "元音", text: "唱「诶」，保持 5 秒", seconds: 6 },
  { stage: "元音", text: "唱「衣」，保持 5 秒", seconds: 6 },
  { stage: "元音", text: "唱「哦」，再唱「乌」，各 5 秒", seconds: 12 },
  { stage: "滑音", text: "用「呜」从低滑到高，再滑回来", seconds: 8 },
  { stage: "滑音", text: "再用「啊」从高滑到低", seconds: 8 },
  { stage: "音阶", text: "用「ma」唱 do re mi fa sol fa mi re do", seconds: 12 },
  { stage: "音阶", text: "换低一点的调，再唱一遍「ma」", seconds: 12 },
  { stage: "音阶", text: "用「mi」唱同一段音阶", seconds: 12 },
  { stage: "歌曲", text: "唱一首你熟悉的慢歌，完整唱一遍，咬字清楚", seconds: 120, flexible: true },
  { stage: "歌曲", text: "换一首不同风格的歌，完整唱一遍", seconds: 120, flexible: true },
  { stage: "歌曲", text: "唱一首偏低、偏安静的歌", seconds: 90, flexible: true },
  { stage: "歌曲", text: "用轻柔假声唱一段高音，不要喊", seconds: 60, flexible: true },
  { stage: "歌曲", text: "再自由清唱一首你喜欢的歌", seconds: 90, flexible: true },
  { stage: "收尾", text: "再唱一句你最舒服的歌，就可以结束了", seconds: 20 },
];

const EASY_STEPS = [
  { stage: "准备", text: "站好，深呼吸，准备开始", seconds: 3 },
  { stage: "哼鸣", text: "闭上嘴哼「嗯——」，保持 8 秒", seconds: 8 },
  { stage: "哼鸣", text: "再哼一次，换高一点的感觉", seconds: 8 },
  { stage: "元音", text: "张嘴唱「啊」，保持 5 秒", seconds: 6 },
  { stage: "元音", text: "高一点再唱「啊」", seconds: 6 },
  { stage: "元音", text: "唱「诶」，保持 5 秒", seconds: 6 },
  { stage: "元音", text: "唱「衣」，保持 5 秒", seconds: 6 },
  { stage: "元音", text: "唱「哦」，再唱「乌」，各 5 秒", seconds: 12 },
  { stage: "滑音", text: "用「呜」从低滑到高，再滑回来", seconds: 8 },
  { stage: "说话", text: "用平时说话的声音，说说你今天做了什么，不用好听", seconds: 30 },
  { stage: "歌曲", text: "唱一首从小就会的歌，比如《小星星》，慢一点，不用好听", seconds: 100, flexible: true },
  { stage: "歌曲", text: "再唱一首简单的歌，或者把刚才那首再唱一遍", seconds: 100, flexible: true },
  { stage: "收尾", text: "再哼一句最舒服的旋律，就结束了", seconds: 15 },
];

const MODES = {
  standard: { label: "标准", steps: STANDARD_STEPS },
  easy: { label: "轻松", steps: EASY_STEPS },
};

const $ = (selector) => document.querySelector(selector);

const state = {
  stream: null,
  recorder: null,
  chunks: [],
  mimeType: "",
  audioContext: null,
  analyser: null,
  meterFrame: 0,
  tickTimer: 0,
  stepIndex: 0,
  stepStart: 0,
  startedAt: 0,
  recording: false,
  finishing: false,
  wakeLock: null,
  pendingBlob: null,
  pendingName: "",
  mode: "standard",
  steps: STANDARD_STEPS,
};

function totalSecondsFor(steps) {
  return steps.reduce((sum, step) => sum + step.seconds, 0);
}

function show(section) {
  ["intro", "studio", "done", "failed"].forEach((id) => {
    $(`#${id}`).hidden = id !== section;
  });
}

function setIntroError(message) {
  const el = $("#intro-error");
  el.textContent = message;
  el.hidden = !message;
}

function formatTime(seconds) {
  const total = Math.max(0, Math.round(seconds));
  const m = String(Math.floor(total / 60)).padStart(2, "0");
  const s = String(total % 60).padStart(2, "0");
  return `${m}:${s}`;
}

function pickMimeType() {
  if (typeof MediaRecorder === "undefined") return "";
  const candidates = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/mp4;codecs=mp4a.40.2",
    "audio/mp4",
    "audio/ogg;codecs=opus",
  ];
  return candidates.find((type) => MediaRecorder.isTypeSupported(type)) || "";
}

function extensionFor(mime) {
  if (mime.includes("webm")) return "webm";
  if (mime.includes("mp4") || mime.includes("aac")) return "mp4";
  if (mime.includes("ogg")) return "ogg";
  return "wav";
}

function renderStep() {
  const step = state.steps[state.stepIndex];
  if (!step) return;
  $("#stage").textContent = step.stage;
  $("#prompt").textContent = step.text;
  $("#step-count").textContent = `${state.stepIndex + 1} / ${state.steps.length}`;
  $("#countdown").textContent = String(Math.ceil(step.seconds));
}

function nextStep() {
  if (!state.recording || state.finishing) return;
  state.stepIndex += 1;
  if (state.stepIndex >= state.steps.length) {
    stopAndUpload(true);
    return;
  }
  state.stepStart = performance.now();
  renderStep();
}

function tick() {
  if (!state.recording) return;
  const now = performance.now();
  const elapsed = (now - state.startedAt) / 1000;
  const inStep = (now - state.stepStart) / 1000;
  const step = state.steps[state.stepIndex];
  const remaining = Math.max(0, step.seconds - inStep);

  $("#elapsed").textContent = formatTime(elapsed);
  $("#countdown").textContent = String(Math.ceil(remaining));

  const stepFraction = Math.min(1, inStep / step.seconds);
  const overall = (state.stepIndex + stepFraction) / state.steps.length;
  $("#progress").style.width = `${Math.min(100, overall * 100).toFixed(2)}%`;

  if (remaining <= 0 && !step.flexible) nextStep();
}

function meterLoop() {
  if (!state.analyser) return;
  const data = new Uint8Array(state.analyser.fftSize);
  const draw = () => {
    if (!state.analyser) return;
    state.analyser.getByteTimeDomainData(data);
    let sum = 0;
    for (let i = 0; i < data.length; i += 1) {
      const value = (data[i] - 128) / 128;
      sum += value * value;
    }
    const rms = Math.sqrt(sum / data.length);
    const width = Math.min(100, rms * 320);
    $("#level-bar").style.width = `${width.toFixed(1)}%`;
    state.meterFrame = requestAnimationFrame(draw);
  };
  draw();
}

function errorMessage(error) {
  if (!error) return "录音失败";
  if (error.name === "NotAllowedError") return "麦克风权限被拒绝。请在浏览器设置里允许麦克风，然后刷新页面。";
  if (error.name === "NotFoundError") return "没有找到麦克风，请检查设备。";
  if (error.name === "NotReadableError") return "麦克风被其他应用占用，请关闭后重试。";
  return `无法开始录音：${error.message || error.name}`;
}

async function startRecording() {
  setIntroError("");
  const name = $("#name").value.trim();
  if (!name) {
    setIntroError("先给这个声音起个名字");
    return;
  }
  if (!$("#consent").checked) {
    setIntroError("请先确认声音为本人所有或已获授权");
    return;
  }
  if (!TOKEN) {
    setIntroError("链接缺少 token，请从 Singer 主界面重新获取录音链接");
    return;
  }
  if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
    setIntroError("浏览器要求 HTTPS 才能录音。请在主界面用隧道生成 https 链接，或在同一台电脑上打开。");
    return;
  }
  if (typeof MediaRecorder === "undefined") {
    setIntroError("这个浏览器不支持录音，请换 Chrome / Edge / Safari 新版本");
    return;
  }

  state.mode = document.querySelector('input[name="mode"]:checked')?.value || "standard";
  state.steps = (MODES[state.mode] || MODES.standard).steps;

  try {
    state.stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: false,
        noiseSuppression: false,
        autoGainControl: false,
        channelCount: 1,
      },
    });
  } catch (error) {
    setIntroError(errorMessage(error));
    return;
  }

  state.mimeType = pickMimeType();
  try {
    state.recorder = new MediaRecorder(
      state.stream,
      state.mimeType ? { mimeType: state.mimeType } : undefined,
    );
  } catch {
    try {
      state.recorder = new MediaRecorder(state.stream);
      state.mimeType = state.recorder.mimeType || state.mimeType;
    } catch (error) {
      setIntroError(`创建录音器失败：${error.message}`);
      return;
    }
  }

  state.chunks = [];
  state.recorder.ondataavailable = (event) => {
    if (event.data && event.data.size > 0) state.chunks.push(event.data);
  };
  state.recorder.onerror = (event) => {
    setIntroError(`录音出错：${event.error?.message || "未知错误"}`);
  };

  state.audioContext = new AudioContext();
  await state.audioContext.resume();
  const source = state.audioContext.createMediaStreamSource(state.stream);
  state.analyser = state.audioContext.createAnalyser();
  state.analyser.fftSize = 1024;
  source.connect(state.analyser);
  meterLoop();

  state.recording = true;
  state.finishing = false;
  state.stepIndex = 0;
  state.startedAt = performance.now();
  state.stepStart = state.startedAt;
  state.recorder.start(1000);
  state.tickTimer = setInterval(tick, 100);

  try {
    state.wakeLock = await navigator.wakeLock.request("screen");
  } catch {
    // 不支持 Wake Lock 就算了，提示用户保持屏幕常亮
  }

  $("#name").blur();
  show("studio");
  renderStep();
}

function stopMedia() {
  state.recording = false;
  clearInterval(state.tickTimer);
  cancelAnimationFrame(state.meterFrame);
  if (state.wakeLock) {
    state.wakeLock.release().catch(() => {});
    state.wakeLock = null;
  }
  if (state.stream) {
    state.stream.getTracks().forEach((track) => track.stop());
    state.stream = null;
  }
  if (state.audioContext) {
    state.audioContext.close().catch(() => {});
    state.audioContext = null;
    state.analyser = null;
  }
}

function stopAndUpload(auto = false) {
  if (!state.recording || state.finishing) return;
  if (!auto && !confirm("结束录音并上传？")) return;

  state.finishing = true;
  $("#rec-state").textContent = "处理中…";
  $("#rec-state").classList.add("paused");

  const recorder = state.recorder;
  const finish = async () => {
    const type = recorder.mimeType || state.mimeType || "audio/webm";
    const blob = new Blob(state.chunks, { type });
    stopMedia();
    if (!blob.size) {
      show("failed");
      $("#failed-text").textContent = "没有录到声音，请检查麦克风后重试。";
      return;
    }
    state.pendingBlob = blob;
    state.pendingName = $("#name").value.trim() || "我的声音";
    await upload();
  };

  recorder.addEventListener("stop", finish, { once: true });
  try {
    recorder.stop();
  } catch {
    finish();
  }
}

async function upload() {
  if (!state.pendingBlob) return;
  show("done");
  $("#done-text").textContent = "正在上传，请稍等…";
  $("#done-stats").innerHTML = "";
  $("#done-warn").hidden = true;

  const extension = extensionFor(state.pendingBlob.type || state.mimeType);
  const data = new FormData();
  data.append("token", TOKEN);
  data.append("name", state.pendingName);
  data.append("consent", "true");
  data.append("mode", state.mode);
  data.append("file", state.pendingBlob, `recording.${extension}`);

  try {
    const response = await fetch("/api/recordings", { method: "POST", body: data });
    const payload = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(payload.detail || `上传失败（${response.status}）`);
    if (payload.status === "processing") {
      await pollStatus(payload.voice_id);
      return;
    }
    showDone(payload);
  } catch (error) {
    show("failed");
    $("#failed-text").textContent = error.message || "上传失败，请检查网络后重试。";
  }
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function pollStatus(voiceId) {
  show("done");
  $("#done-text").textContent = "录音已上传，正在切片和质检，请稍等…";
  $("#done-stats").innerHTML = "";
  $("#done-warn").hidden = true;

  for (let attempt = 0; attempt < 180; attempt += 1) {
    await sleep(2000);
    try {
      const response = await fetch(
        `/api/recordings/${encodeURIComponent(voiceId)}/status?token=${encodeURIComponent(TOKEN)}`,
      );
      const data = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(data.detail || "查询状态失败");
      if (data.status === "ready") {
        showDone(data);
        return;
      }
      if (data.status === "failed") {
        show("failed");
        $("#failed-text").textContent = `切片失败：${data.error || "请回到主界面点「准备训练」重试"}`;
        return;
      }
    } catch {
      // 网络抖动时继续轮询
    }
  }

  show("failed");
  $("#failed-text").textContent = "切片时间较长，请稍后回到 Singer 主界面点「准备训练」重试。";
}

function showDone(payload) {
  show("done");
  $("#done-text").textContent = "录音已经保存到这台电脑，并自动切好片。";
  const warnings = Array.isArray(payload.warnings) ? payload.warnings : [];
  const items = [
    [formatTime(payload.duration || 0), "录到的总时长"],
    [String(payload.clip_count ?? "-"), "有效切片"],
    [formatTime(payload.total_seconds || 0), "可用演唱"],
  ];
  $("#done-stats").innerHTML = items
    .map(
      ([value, label]) =>
        `<div class="done-stat"><b>${escapeHtml(value)}</b><span>${escapeHtml(label)}</span></div>`,
    )
    .join("");
  const warn = $("#done-warn");
  warn.textContent = warnings[0] || "";
  warn.hidden = !warnings.length;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function init() {
  const conn = $("#conn");
  if (!TOKEN) {
    conn.textContent = "链接无效";
    conn.classList.add("bad");
    setIntroError("链接缺少 token，请从 Singer 主界面重新获取录音链接。");
  } else if (window.isSecureContext) {
    conn.textContent = "可以录音";
    conn.classList.add("ok");
  } else {
    conn.textContent = "需要 HTTPS";
    conn.classList.add("bad");
  }

  $("#start").addEventListener("click", startRecording);
  $("#next").addEventListener("click", nextStep);
  $("#stop").addEventListener("click", () => stopAndUpload(false));
  $("#retry").addEventListener("click", upload);
  $("#name").addEventListener("keydown", (event) => {
    if (event.key === "Enter") startRecording();
  });

  window.addEventListener("beforeunload", (event) => {
    if (state.recording) {
      event.preventDefault();
      event.returnValue = "";
    }
  });

  document.querySelectorAll('input[name="mode"]').forEach((input) => {
    input.addEventListener("change", updateIntroHint);
  });
  updateIntroHint();
}

function updateIntroHint() {
  const mode = document.querySelector('input[name="mode"]:checked')?.value || "standard";
  const total = totalSecondsFor((MODES[mode] || MODES.standard).steps);
  $("#intro-hint").textContent = `全程约 ${Math.round(total / 60)} 分钟，可以随时点“结束并上传”。需要麦克风权限，手机请保持屏幕常亮。`;
}

init();

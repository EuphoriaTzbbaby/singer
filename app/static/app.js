const $ = (selector) => document.querySelector(selector);

const state = {
  voices: [],
  songs: [],
};

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatDuration(seconds) {
  const total = Math.round(Number(seconds) || 0);
  if (total < 60) return `${total} 秒`;
  const m = Math.floor(total / 60);
  const s = total % 60;
  return s ? `${m} 分 ${s} 秒` : `${m} 分钟`;
}

function formatDate(iso) {
  if (!iso) return "";
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

async function api(path, options = {}) {
  const response = await fetch(path, options);
  const type = response.headers.get("content-type") || "";
  const data = type.includes("application/json") ? await response.json() : await response.text();
  if (!response.ok) {
    let message = response.statusText;
    if (typeof data === "string" && data) message = data;
    if (data && typeof data === "object" && data.detail) {
      message = Array.isArray(data.detail)
        ? data.detail.map((d) => d.msg || JSON.stringify(d)).join("；")
        : String(data.detail);
    }
    throw new Error(message || `请求失败（${response.status}）`);
  }
  return data;
}

let toastTimer = null;
function toast(message, bad = false) {
  const el = $("#toast");
  el.textContent = message;
  el.classList.toggle("bad", bad);
  el.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => {
    el.hidden = true;
  }, 3600);
}

function setBusy(form, busy, label) {
  const button = form.querySelector("button[type=submit]");
  if (!button) return;
  if (!button.dataset.label) button.dataset.label = button.textContent;
  button.disabled = busy;
  button.textContent = busy ? label : button.dataset.label;
}

async function refreshHealth() {
  const pill = $("#health");
  try {
    const data = await api("/api/health");
    pill.textContent = `已连接 · ${data.voice_count} 个音色 / ${data.song_count} 首歌`;
    pill.classList.add("ok");
    pill.classList.remove("bad");
  } catch (error) {
    pill.textContent = "服务未连接";
    pill.classList.add("bad");
    pill.classList.remove("ok");
  }
}

function renderVoices() {
  const list = $("#voice-list");
  if (!state.voices.length) {
    list.innerHTML = '<p class="empty">还没有音色素材</p>';
    return;
  }
  list.innerHTML = state.voices
    .map((voice) => {
      const badge = voice.has_model
        ? '<span class="tag ok">模型就绪</span>'
        : '<span class="tag warn">待训练 / 导入模型</span>';
      const count = Array.isArray(voice.files) ? voice.files.length : 0;
      const sub = `${count} 个文件 · ${formatDuration(voice.total_duration)} · ${formatDate(voice.created_at)}`;
      return `
        <div class="item" data-id="${escapeHtml(voice.id)}">
          <div class="item-main">
            <div class="item-title">${escapeHtml(voice.name)}${badge}</div>
            <div class="item-sub">${escapeHtml(sub)}</div>
          </div>
          <button class="ghost" data-delete-voice="${escapeHtml(voice.id)}">删除</button>
        </div>`;
    })
    .join("");
}

function renderSongs() {
  const list = $("#song-list");
  if (!state.songs.length) {
    list.innerHTML = '<p class="empty">还没有上传歌曲</p>';
    return;
  }
  list.innerHTML = state.songs
    .map((song) => {
      const name = song.artist ? `${song.title} — ${song.artist}` : song.title;
      const sub = `${formatDuration(song.duration)} · ${formatDate(song.created_at)}`;
      return `
        <div class="item" data-id="${escapeHtml(song.id)}">
          <div class="item-main">
            <div class="item-title">${escapeHtml(name)}</div>
            <div class="item-sub">${escapeHtml(sub)}</div>
          </div>
          <button class="ghost" data-delete-song="${escapeHtml(song.id)}">删除</button>
        </div>`;
    })
    .join("");
}

function renderPickers() {
  const voiceSelect = $("#pick-voice");
  const songSelect = $("#pick-song");
  const readyVoices = state.voices.filter((voice) => voice.has_model);

  const currentVoice = voiceSelect.value;
  voiceSelect.innerHTML =
    '<option value="">选择已就绪的音色</option>' +
    readyVoices
      .map((voice) => `<option value="${escapeHtml(voice.id)}">${escapeHtml(voice.name)}</option>`)
      .join("");

  const currentSong = songSelect.value;
  songSelect.innerHTML =
    '<option value="">选择歌曲</option>' +
    state.songs
      .map(
        (song) =>
          `<option value="${escapeHtml(song.id)}">${escapeHtml(
            song.artist ? `${song.title} — ${song.artist}` : song.title,
          )}</option>`,
      )
      .join("");

  if (readyVoices.some((voice) => voice.id === currentVoice)) voiceSelect.value = currentVoice;
  if (state.songs.some((song) => song.id === currentSong)) songSelect.value = currentSong;
}

async function loadVoices() {
  state.voices = await api("/api/voices");
  renderVoices();
  renderPickers();
}

async function loadSongs() {
  state.songs = await api("/api/songs");
  renderSongs();
  renderPickers();
}

async function handleVoiceSubmit(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = new FormData(form);
  const button = form.querySelector("button[type=submit]");
  const files = data.getAll("files").filter((file) => file.size > 0);
  if (!files.length) {
    toast("请选择至少一个音频文件", true);
    return;
  }

  setBusy(form, true, "上传并转码中…");
  try {
    const result = await api("/api/voices", { method: "POST", body: data });
    form.reset();
    await loadVoices();
    await refreshHealth();
    const warning = result.warnings && result.warnings[0];
    toast(warning || "声音素材已保存", Boolean(warning));
  } catch (error) {
    toast(error.message, true);
  } finally {
    setBusy(form, false);
  }
}

async function handleSongSubmit(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = new FormData(form);
  setBusy(form, true, "上传并转码中…");
  try {
    await api("/api/songs", { method: "POST", body: data });
    form.reset();
    await loadSongs();
    await refreshHealth();
    toast("歌曲已上传");
  } catch (error) {
    toast(error.message, true);
  } finally {
    setBusy(form, false);
  }
}

async function handleListClick(event) {
  const voiceButton = event.target.closest("[data-delete-voice]");
  if (voiceButton) {
    const id = voiceButton.dataset.deleteVoice;
    if (!confirm("删除这个音色及全部素材？此操作不可恢复。")) return;
    try {
      await api(`/api/voices/${id}`, { method: "DELETE" });
      await loadVoices();
      await refreshHealth();
      toast("音色已删除");
    } catch (error) {
      toast(error.message, true);
    }
    return;
  }

  const songButton = event.target.closest("[data-delete-song]");
  if (songButton) {
    const id = songButton.dataset.deleteSong;
    if (!confirm("删除这首歌？此操作不可恢复。")) return;
    try {
      await api(`/api/songs/${id}`, { method: "DELETE" });
      await loadSongs();
      await refreshHealth();
      toast("歌曲已删除");
    } catch (error) {
      toast(error.message, true);
    }
  }
}

async function init() {
  $("#voice-form").addEventListener("submit", handleVoiceSubmit);
  $("#song-form").addEventListener("submit", handleSongSubmit);
  $("#voice-list").addEventListener("click", handleListClick);
  $("#song-list").addEventListener("click", handleListClick);

  await refreshHealth();
  try {
    await Promise.all([loadVoices(), loadSongs()]);
  } catch (error) {
    toast(`加载数据失败：${error.message}`, true);
  }
}

init();

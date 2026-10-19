"""应用配置：路径、端口、上传限制。"""

from __future__ import annotations

import secrets
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="SINGER_",
        env_file=ROOT / ".env",
        extra="ignore",
    )

    host: str = "127.0.0.1"
    port: int = 8765

    data_dir: Path = ROOT / "data"
    models_dir: Path = ROOT / "models"
    static_dir: Path = ROOT / "app" / "static"
    cache_dir: Path = ROOT / ".cache"

    ffmpeg: str = "ffmpeg"
    ffprobe: str = "ffprobe"
    max_upload_mb: int = 500

    # 远程录音：URL 里的访问令牌；留空则自动生成到 data/record_token.txt
    record_token: str = ""
    # 远程访问时是否开放完整管理界面（默认只开放录音页）
    allow_remote_admin: bool = False

    # 人声分离
    demucs_model: str = "htdemucs_ft"
    demucs_device: str = "auto"  # auto / mps / cpu

    @property
    def torch_home(self) -> Path:
        return self.cache_dir / "torch"

    @property
    def voices_dir(self) -> Path:
        return self.data_dir / "voices"

    @property
    def songs_dir(self) -> Path:
        return self.data_dir / "songs"

    @property
    def jobs_dir(self) -> Path:
        return self.data_dir / "jobs"

    def ensure_record_token(self) -> str:
        """读取或生成录音页令牌，写入 data/record_token.txt。"""
        if self.record_token:
            return self.record_token
        token_file = self.data_dir / "record_token.txt"
        if token_file.exists():
            token = token_file.read_text(encoding="utf-8").strip()
            if token:
                self.record_token = token
                return token
        token = secrets.token_urlsafe(18)
        token_file.write_text(token + "\n", encoding="utf-8")
        self.record_token = token
        return token

    def ensure_dirs(self) -> None:
        for path in (
            self.data_dir,
            self.voices_dir,
            self.songs_dir,
            self.jobs_dir,
            self.models_dir,
            self.cache_dir,
            self.torch_home,
            self.cache_dir / "xdg",
            self.cache_dir / "huggingface",
        ):
            path.mkdir(parents=True, exist_ok=True)


settings = Settings()

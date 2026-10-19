"""应用配置：路径、端口、上传限制。"""

from __future__ import annotations

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

    ffmpeg: str = "ffmpeg"
    ffprobe: str = "ffprobe"
    max_upload_mb: int = 500

    @property
    def voices_dir(self) -> Path:
        return self.data_dir / "voices"

    @property
    def songs_dir(self) -> Path:
        return self.data_dir / "songs"

    @property
    def jobs_dir(self) -> Path:
        return self.data_dir / "jobs"

    def ensure_dirs(self) -> None:
        for path in (
            self.data_dir,
            self.voices_dir,
            self.songs_dir,
            self.jobs_dir,
            self.models_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


settings = Settings()

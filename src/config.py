"""Read settings without exposing credentials in representations or errors."""

import os
from pathlib import Path
from typing import Literal
from urllib.parse import urlsplit

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, SecretStr, field_validator


class ConfigurationError(ValueError):
    pass


class Settings(BaseModel):
    model_config = ConfigDict(frozen=True)

    api_key: SecretStr = Field(default_factory=lambda: SecretStr(""))
    base_url: str = ""
    model_name: str = ""
    backend: Literal["auto", "mock", "real", "local"] = "auto"
    local_model: str = "Qwen/Qwen2.5-0.5B-Instruct"
    local_adapter: str = ""
    app_username: str = ""
    app_password: SecretStr = Field(default_factory=lambda: SecretStr(""))
    timeout_seconds: float = Field(default=30, ge=1, le=180)
    max_output_tokens: int = Field(default=2500, ge=256, le=8192)
    host: str = "127.0.0.1"
    share: bool = False
    port: int = Field(default=7860, ge=1, le=65535)

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, value: str) -> str:
        if not value:
            return value
        try:
            parsed = urlsplit(value)
            _ = parsed.port
        except ValueError:
            raise ValueError("MODEL_BASE_URL 不是有效地址") from None
        if (
            parsed.scheme not in {"http", "https"}
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.query
            or parsed.fragment
        ):
            raise ValueError("MODEL_BASE_URL 需为不含凭据、查询参数和片段的 HTTP(S) 地址")
        if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1", "::1"}:
            raise ValueError("远程 MODEL_BASE_URL 必须使用 HTTPS；本机接口允许 HTTP")
        return value.rstrip("/")

    @property
    def effective_backend(self) -> Literal["mock", "real", "local"]:
        if self.backend == "local":
            return "local"
        if self.backend == "mock":
            return "mock"
        present = [bool(self.api_key.get_secret_value()), bool(self.base_url), bool(self.model_name)]
        if all(present):
            return "real"
        if self.backend == "auto" and not any(present):
            return "mock"
        raise ConfigurationError("真实模型配置不完整：请同时设置 MODEL_API_KEY、MODEL_BASE_URL 和 MODEL_NAME；或明确设置 SHELLGUARD_BACKEND=mock。")


def load_settings() -> Settings:
    # Only the project's .env is loaded; existing process variables take priority.
    load_dotenv(Path(__file__).resolve().parents[1] / ".env", override=False)
    return Settings(
        api_key=SecretStr(os.getenv("MODEL_API_KEY", "").strip()),
        base_url=os.getenv("MODEL_BASE_URL", "").strip(),
        model_name=os.getenv("MODEL_NAME", "").strip(),
        backend=os.getenv("SHELLGUARD_BACKEND", "auto").strip().lower(),
        timeout_seconds=os.getenv("MODEL_TIMEOUT_SECONDS", "30"),
        max_output_tokens=os.getenv("MODEL_MAX_OUTPUT_TOKENS", "2500"),
        share=os.getenv("APP_SHARE", "false"),
        host=os.getenv("APP_HOST", "127.0.0.1"),
        port=os.getenv("APP_PORT", "7860"),
        local_model=os.getenv("LOCAL_MODEL", "Qwen/Qwen2.5-0.5B-Instruct").strip(),
        local_adapter=os.getenv("LOCAL_ADAPTER", "").strip(),
        app_username=os.getenv("APP_USERNAME", "").strip(),
        app_password=SecretStr(os.getenv("APP_PASSWORD", "")),
    )

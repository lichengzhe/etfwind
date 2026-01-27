"""配置管理模块"""

from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional


class Settings(BaseSettings):
    """应用配置"""

    # Claude API 配置
    claude_api_key: str = Field(..., alias="CLAUDE_API_KEY")
    claude_base_url: str = Field(
        default="https://code.newcli.com/claude/aws", alias="CLAUDE_BASE_URL"
    )
    claude_model: str = Field(
        default="claude-opus-4-5", alias="CLAUDE_MODEL"
    )

    # Supabase 配置
    supabase_url: str = Field(..., alias="SUPABASE_URL")
    supabase_key: str = Field(..., alias="SUPABASE_KEY")

    # 企业微信配置
    wecom_webhook_url: Optional[str] = Field(default=None, alias="WECOM_WEBHOOK_URL")

    # 邮件配置
    smtp_host: Optional[str] = Field(default=None, alias="SMTP_HOST")
    smtp_port: int = Field(default=465, alias="SMTP_PORT")
    smtp_user: Optional[str] = Field(default=None, alias="SMTP_USER")
    smtp_password: Optional[str] = Field(default=None, alias="SMTP_PASSWORD")
    email_recipients: Optional[str] = Field(default=None, alias="EMAIL_RECIPIENTS")

    @property
    def email_recipient_list(self) -> list[str]:
        """获取邮件收件人列表"""
        if not self.email_recipients:
            return []
        return [e.strip() for e in self.email_recipients.split(",") if e.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()

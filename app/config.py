from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    gmail_client_id: str
    gmail_client_secret: str
    gmail_token_file: str = "token.json"

    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3:70b"

    postgres_url: str
    postgres_password: str = ""

    summary_email_to: str
    summary_email_from: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""

    schedule_times: str = "08:00,11:00,14:00,17:00,20:00"

    @property
    def schedule_times_list(self) -> list[tuple[int, int]]:
        result = []
        for t in self.schedule_times.split(","):
            h, m = t.strip().split(":")
            result.append((int(h), int(m)))
        return result


settings = Settings()

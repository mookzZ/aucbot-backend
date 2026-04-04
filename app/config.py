from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str
    bot_token: str
    stalcraft_client_id: str
    stalcraft_client_secret: str
    stalcraft_api_url: str = "https://eapi.stalcraft.net"
    stalcraft_auth_url: str = "https://exbo.net/oauth/token"
    github_token: str = ""

    class Config:
        env_file = ".env"


settings = Settings()

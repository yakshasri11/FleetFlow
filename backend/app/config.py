from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:YOUR_PASSWORD@localhost:5432/fleetflow_db"

    class Config:
        env_file = "../.env"

settings = Settings()

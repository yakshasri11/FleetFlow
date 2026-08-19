from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql://postgres:YOUR_PASSWORD@localhost:5432/fleetflow_db"
    redis_url: str = "redis://localhost:6379/0"
    secret_key: str = "change-this-secret-key-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    # Optional — leave blank to run entirely on the free local route-estimation
    # fallback (haversine distance + assumed speeds). Set it to use live Google
    # Maps Directions/Geocoding for real distances, traffic and ETAs.
    google_maps_api_key: str = ""
    # Comma-separated list of allowed frontend origins, e.g.
    # "https://fleetflow.vercel.app,http://127.0.0.1:5500". Defaults to "*"
    # (any origin) for easy local/demo use — lock this down to your real
    # frontend URL(s) in production.
    cors_origins: str = "*"

    class Config:
        env_file = ".env"


settings = Settings()

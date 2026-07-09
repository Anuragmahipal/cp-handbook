from pathlib import Path
import tomllib


class Settings:
    def __init__(self):
        config_path = Path(__file__).resolve().parents[2] / "config" / "settings.toml"

        with open(config_path, "rb") as f:
            config = tomllib.load(f)

        self.vault = config["vault"]
        self.git = config["git"]
        self.templates = config["templates"]
        self.notes = config["notes"]


settings = Settings()

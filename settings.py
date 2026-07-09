from pathlib import Path
import tomllib

PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings:
    def __init__(self):
        config_file = PROJECT_ROOT / "config" / "settings.toml"

        with open(config_file, "rb") as f:
            self._config = tomllib.load(f)

    @property
    def vault_path(self) -> Path:
        return Path(self._config["vault"]["path"])

    @property
    def template_path(self) -> Path:
        return PROJECT_ROOT / self._config["templates"]["path"]

    @property
    def notes(self):
        return self._config["notes"]

    @property
    def git(self):
        return self._config["git"]


settings = Settings()

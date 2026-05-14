from dataclasses import dataclass
from pathlib import Path

from app.logger import get_logger


logger = get_logger(__name__)


@dataclass(frozen=True)
class ModelCheckResult:
    provider: str
    model: str
    is_ready: bool
    message: str


class ModelManager:
    """
    Checks whether local AI models are already downloaded.

    This does NOT download models.
    It only checks the local Hugging Face cache.
    """

    def __init__(self):
        self.hf_cache_dir = Path.home() / ".cache" / "huggingface" / "hub"

    def check_local_whisper_model(self, model_name: str) -> ModelCheckResult:
        """
        Checks faster-whisper models from Hugging Face cache.

        Examples:
        - tiny
        - base
        - small
        - medium
        - large-v3
        """

        if not self.hf_cache_dir.exists():
            return ModelCheckResult(
                provider="local",
                model=model_name,
                is_ready=False,
                message="Hugging Face cache not found.",
            )

        possible_cache_names = [
            f"models--Systran--faster-whisper-{model_name}",
            f"models--guillaumekln--faster-whisper-{model_name}",
        ]

        for cache_name in possible_cache_names:
            cache_path = self.hf_cache_dir / cache_name

            if self.is_valid_hf_model_cache(cache_path):
                return ModelCheckResult(
                    provider="local",
                    model=model_name,
                    is_ready=True,
                    message="Whisper model is downloaded.",
                )

        return ModelCheckResult(
            provider="local",
            model=model_name,
            is_ready=False,
            message="Whisper model is not downloaded yet.",
        )

    def check_nllb_model(self, model_name: str) -> ModelCheckResult:
        """
        Checks NLLB translation model from Hugging Face cache.

        Example:
        facebook/nllb-200-distilled-600M
        """

        if not self.hf_cache_dir.exists():
            return ModelCheckResult(
                provider="local_nllb",
                model=model_name,
                is_ready=False,
                message="Hugging Face cache not found.",
            )

        cache_name = "models--" + model_name.replace("/", "--")
        cache_path = self.hf_cache_dir / cache_name

        if self.is_valid_hf_model_cache(cache_path):
            return ModelCheckResult(
                provider="local_nllb",
                model=model_name,
                is_ready=True,
                message="Translation model is downloaded.",
            )

        return ModelCheckResult(
            provider="local_nllb",
            model=model_name,
            is_ready=False,
            message="Translation model is not downloaded yet.",
        )
    
    def check_voxcpm_model(
        self,
        model_name: str = "openbmb/VoxCPM2",
    ) -> ModelCheckResult:
        """
        Checks VoxCPM2 model from Hugging Face cache.

        Example:
        openbmb/VoxCPM2
        """

        if not self.hf_cache_dir.exists():
            return ModelCheckResult(
                provider="local_voxcpm",
                model=model_name,
                is_ready=False,
                message="Hugging Face cache not found.",
            )

        cache_name = "models--" + model_name.replace("/", "--")
        cache_path = self.hf_cache_dir / cache_name

        if self.is_valid_hf_model_cache(cache_path):
            return ModelCheckResult(
                provider="local_voxcpm",
                model=model_name,
                is_ready=True,
                message="VoxCPM2 model is downloaded.",
            )

        return ModelCheckResult(
            provider="local_voxcpm",
            model=model_name,
            is_ready=False,
            message="VoxCPM2 model is not downloaded yet.",
        )

    def is_valid_hf_model_cache(self, cache_path: Path) -> bool:
        """
        Hugging Face model cache usually has:
        - blobs/
        - refs/
        - snapshots/

        We check snapshots because that means at least one model revision exists locally.
        """

        if not cache_path.exists():
            return False

        snapshots_dir = cache_path / "snapshots"

        if not snapshots_dir.exists():
            return False

        snapshots = list(snapshots_dir.iterdir())

        return len(snapshots) > 0
"""llm-iq-bench: 大语言模型多维度能力评测框架。"""
from .config import load_config, CONFIG_DIR
from .models import build_model_client
from .datasets import load_dataset_samples
from .metrics import compute_metric
from .runner import Runner

__version__ = "0.1.0"
__all__ = ["load_config", "build_model_client", "load_dataset_samples", "compute_metric", "Runner"]

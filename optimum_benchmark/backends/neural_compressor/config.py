from dataclasses import dataclass, field
from typing import Any, Dict

from omegaconf import OmegaConf

from ...import_utils import neural_compressor_version
from ..config import BackendConfig

OmegaConf.register_new_resolver("neural_compressor_version", neural_compressor_version)

# https://github.com/intel/neural-compressor/blob/master/neural_compressor/config.py#L490
ACCURACY_CRITERION_CONFIG = {
    "higher_is_better": True,
    "criterion": "relative",
    "tolerable_loss": 0.01,
}

# https://github.com/intel/neural-compressor/blob/master/neural_compressor/config.py#L593
TUNING_CRITERION_CONFIG = {
    "strategy": "basic",
    "strategy_kwargs": None,
    "timeout": 0,
    "max_trials": 100,
    "objective": "performance",
}

# https://github.com/intel/neural-compressor/blob/master/neural_compressor/config.py#L1242
PTQ_QUANTIZATION_CONFIG = {
    "device": "cpu",
    "backend": "default",
    "domain": "auto",
    "recipes": {},
    "quant_format": "default",
    "inputs": [],
    "outputs": [],
    "approach": "static",
    "calibration_sampling_size": [100],
    "op_type_dict": None,
    "op_name_dict": None,
    "reduce_range": None,
    "example_inputs": None,
    "excluded_precisions": [],
    "quant_level": "auto",
    "accuracy_criterion": ACCURACY_CRITERION_CONFIG,
    "tuning_criterion": TUNING_CRITERION_CONFIG,
    "diagnosis": False,
}


CALIBRATION_CONFIG = {
    "dataset_name": "glue",
    "num_samples": 300,
    "dataset_config_name": "sst2",
    "dataset_split": "train",
    "preprocess_batch": True,
    "preprocess_class": "optimum_benchmark.preprocessors.glue.GluePreprocessor",
}


@dataclass
class INCConfig(BackendConfig):
    name: str = "neural_compressor"
    version: str = "${neural_compressor_version:}"
    _target_: str = "optimum_benchmark.backends.neural_compressor.backend.INCBackend"

    # post-training quantization options
    ptq_quantization: bool = False
    ptq_quantization_config: Dict[str, Any] = field(default_factory=dict)

    # calibration options
    calibration: bool = False
    calibration_config: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if self.ptq_quantization:
            self.ptq_quantization_config = OmegaConf.to_object(
                OmegaConf.merge(PTQ_QUANTIZATION_CONFIG, self.ptq_quantization_config)
            )
            if self.ptq_quantization_config["approach"] == "static" and not self.calibration:
                raise ValueError("Calibration must be enabled when using static quantization.")

        if self.calibration:
            self.calibration_config = OmegaConf.to_object(OmegaConf.merge(CALIBRATION_CONFIG, self.calibration_config))

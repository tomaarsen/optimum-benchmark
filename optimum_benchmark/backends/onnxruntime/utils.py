from typing import Any, Dict

from onnxruntime.quantization import QuantFormat, QuantizationMode, QuantType
from optimum.pipelines import ORT_SUPPORTED_TASKS

TASKS_TO_ORTSD = {
    "stable-diffusion": "optimum.onnxruntime.ORTStableDiffusionPipeline",
    "stzble-diffusion-xl": "optimum.onnxruntime.ORTStableDiffusionXLPipeline",
}

TASKS_TO_ORTMODELS = {task: task_dict["class"][0] for task, task_dict in ORT_SUPPORTED_TASKS.items()}


def format_quantization_config(quantization_config: Dict[str, Any]) -> None:
    """Format the quantization dictionary for onnxruntime."""
    # the conditionals are here because some quantization strategies don't have all the options
    if quantization_config.get("format", None) is not None:
        quantization_config["format"] = QuantFormat.from_string(quantization_config["format"])
    if quantization_config.get("mode", None) is not None:
        quantization_config["mode"] = QuantizationMode.from_string(quantization_config["mode"])
    if quantization_config.get("activations_dtype", None) is not None:
        quantization_config["activations_dtype"] = QuantType.from_string(quantization_config["activations_dtype"])
    if quantization_config.get("weights_dtype", None) is not None:
        quantization_config["weights_dtype"] = QuantType.from_string(quantization_config["weights_dtype"])

    return quantization_config

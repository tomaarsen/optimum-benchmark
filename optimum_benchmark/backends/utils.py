import os
import signal
import subprocess
import time
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

if TYPE_CHECKING:
    from transformers import (
        FeatureExtractionMixin,
        ImageProcessingMixin,
        Pipeline,
        PretrainedConfig,
        PreTrainedTokenizer,
        ProcessorMixin,
    )

    PreTrainedProcessor = Union[
        PreTrainedTokenizer,
        ImageProcessingMixin,
        FeatureExtractionMixin,
        ProcessorMixin,
    ]


def extract_shapes_from_diffusion_pipeline(pipeline: "Pipeline") -> Dict[str, Any]:
    # this is the only way I found to extract a diffusion pipeline's "input" shapes
    shapes = {}
    if hasattr(pipeline, "vae_encoder") and hasattr(pipeline.vae_encoder, "config"):
        shapes["num_channels"] = pipeline.vae_encoder.config["out_channels"]
        shapes["height"] = pipeline.vae_encoder.config["sample_size"]
        shapes["width"] = pipeline.vae_encoder.config["sample_size"]
    elif hasattr(pipeline, "vae") and hasattr(pipeline.vae, "config"):
        shapes["num_channels"] = pipeline.vae.config.out_channels
        shapes["height"] = pipeline.vae.config.sample_size
        shapes["width"] = pipeline.vae.config.sample_size
    else:
        shapes["num_channels"] = -1
        shapes["height"] = -1
        shapes["width"] = -1

    return shapes


def extract_shapes_from_model_artifacts(
    config: "PretrainedConfig", processor: Optional["PreTrainedProcessor"] = None
) -> Dict[str, Any]:
    shapes = {}
    artifacts_dict = {}

    config_dict = {k: v for k, v in config.to_dict().items() if v is not None}
    artifacts_dict.update(config_dict)

    if processor is not None and hasattr(processor, "to_dict"):
        processor_dict = {k: v for k, v in processor.to_dict().items() if v is not None}
        artifacts_dict.update(processor_dict)

    # text input
    shapes["vocab_size"] = artifacts_dict.get("vocab_size", 2)
    shapes["type_vocab_size"] = artifacts_dict.get("type_vocab_size", 2)

    # image input
    shapes["num_channels"] = artifacts_dict.get("num_channels", None)

    image_size = artifacts_dict.get("image_size", None)
    if image_size is None:
        # processors have different names for the image size
        image_size = artifacts_dict.get("size", None)

    if isinstance(image_size, (int, float)):
        shapes["height"] = image_size
        shapes["width"] = image_size
    elif isinstance(image_size, (list, tuple)):
        shapes["height"] = image_size[0]
        shapes["width"] = image_size[0]
    elif isinstance(image_size, dict) and len(image_size) == 2:
        shapes["height"] = list(image_size.values())[0]
        shapes["width"] = list(image_size.values())[1]
    elif isinstance(image_size, dict) and len(image_size) == 1:
        shapes["height"] = list(image_size.values())[0]
        shapes["width"] = list(image_size.values())[0]
    else:
        shapes["height"] = None
        shapes["width"] = None

    # classification labels (default to 2)
    shapes["num_labels"] = len(artifacts_dict.get("id2label", {"0": "LABEL_0", "1": "LABEL_1"}))

    # object detection labels (default to 2)
    shapes["num_queries"] = artifacts_dict.get("num_queries", 2)

    return shapes


def check_no_process_is_running_on_cuda_device(device_ids: List[int]) -> None:
    """Raises a RuntimeError if any process is running on the given cuda device."""
    for device_id in device_ids:
        # get list of all PIDs running on nvidia devices
        pids = [
            int(pid)
            for pid in subprocess.check_output(["nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader"])
            .decode()
            .strip()
            .split("\n")
            if pid != ""
        ]

        # get list of PIDs running on cuda device_id
        pids_on_device_id = {
            pid
            for pid in pids
            if subprocess.check_output(
                [
                    "nvidia-smi",
                    "--query-compute-apps=pid,used_memory",
                    "--format=csv,noheader,nounits",
                    f"--id={device_id}",
                ]
            )
            .decode()
            .startswith(f"{pid},")
        }

        # TODO: It would be safer to run each run of a sweep in a subprocess.
        # Although we can trust PyTorch to clear GPU memory when asked,
        # it is not a safe assumption to make for all backends.
        if len(pids_on_device_id) > 1 or (len(pids_on_device_id) == 1 and os.getpid() not in pids_on_device_id):
            raise RuntimeError(
                f"Expected no processes on device {device_id}, "
                f"found {len(pids_on_device_id)} processes "
                f"with PIDs {pids_on_device_id}."
            )


def check_only_this_process_is_running_on_cuda_device(device_ids: List[int], pid) -> None:
    """Raises a RuntimeError if at any point in time, there is a process running
    on the given cuda device that is not the current process.
    """
    while True:
        # get list of all PIDs running on nvidia devices
        pids = [
            int(pid)
            for pid in subprocess.check_output(["nvidia-smi", "--query-compute-apps=pid", "--format=csv,noheader"])
            .decode()
            .strip()
            .split("\n")
            if pid != ""
        ]

        for device_id in device_ids:
            # get list of PIDs running on cuda device_id
            pids_on_device_id = {
                pid
                for pid in pids
                if subprocess.check_output(
                    [
                        "nvidia-smi",
                        "--query-compute-apps=pid,used_memory",
                        "--format=csv,noheader,nounits",
                        f"--id={device_id}",
                    ]
                )
                .decode()
                .startswith(f"{pid},")
            }

            # check if there is a process running on device_id that is not the current process
            if len(pids_on_device_id) > 1:
                os.kill(pid, signal.SIGTERM)
                raise RuntimeError(
                    f"Expected only process {pid} on device {device_id}, "
                    f"found {len(pids_on_device_id)} processes "
                    f"with PIDs {pids_on_device_id}."
                )

        # sleep for 1 second
        time.sleep(1)

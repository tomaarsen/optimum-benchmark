import os
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable, Dict, Optional, Union

import torch
from optimum.exporters.onnx.__main__ import (
    DEFAULT_DUMMY_SHAPES,
    ONNX_WEIGHTS_NAME,
    # UNPICKABLE_ARCHS,
    # AtolError,
    AutoTokenizer,
    OnnxConfigWithPast,
    # OutputMatchError,
    RequestsConnectionError,
    # ShapeError,
    TasksManager,
    _get_submodels_and_onnx_configs,
    export_models,
    is_torch_available,
    logger,
    maybe_load_preprocessors,
    maybe_save_preprocessors,
)

if TYPE_CHECKING:
    from optimum.exporters.onnx import OnnxConfig
    from transformers import PreTrainedModel


# rewrite of the main_export function from optimum.exporters.onnx.__main__
# to use the model passed in as an argument instead of loading it from the model_name_or_path
def main_export(
    model_name_or_path: str,
    output: Union[str, Path],
    task: str = "auto",
    opset: Optional[int] = None,
    device: str = "cpu",
    fp16: Optional[bool] = False,
    optimize: Optional[str] = None,
    monolith: bool = False,
    no_post_process: bool = False,
    framework: Optional[str] = None,
    atol: Optional[float] = None,
    cache_dir: Optional[str] = None,
    trust_remote_code: bool = False,
    pad_token_id: Optional[int] = None,
    subfolder: str = "",
    revision: str = "main",
    force_download: bool = False,
    local_files_only: bool = False,
    use_auth_token: Optional[Union[bool, str]] = None,
    for_ort: bool = False,
    do_validation: bool = True,
    model_kwargs: Optional[Dict[str, Any]] = None,
    custom_onnx_configs: Optional[Dict[str, "OnnxConfig"]] = None,
    fn_get_submodels: Optional[Callable] = None,
    use_subprocess: bool = False,
    _variant: str = "default",
    ########################################
    model: Optional["PreTrainedModel"] = None,
    ########################################
    **kwargs_shapes,
):
    """
    Full-suite ONNX export.

    Args:
        > Required parameters

        model_name_or_path (`str`):
            Model ID on huggingface.co or path on disk to the model repository to export.
        output (`Union[str, Path]`):
            Path indicating the directory where to store the generated ONNX model.

        > Optional parameters

        task (`Optional[str]`, defaults to `None`):
            The task to export the model for. If not specified, the task will be auto-inferred based on the model. For decoder models,
            use `xxx-with-past` to export the model using past key values in the decoder.
        opset (`Optional[int]`, defaults to `None`):
            If specified, ONNX opset version to export the model with. Otherwise, the default opset for the given model architecture
            will be used.
        device (`str`, defaults to `"cpu"`):
            The device to use to do the export. Defaults to "cpu".
        fp16 (`Optional[bool]`, defaults to `"False"`):
            Use half precision during the export. PyTorch-only, requires `device="cuda"`.
        optimize (`Optional[str]`, defaults to `None`):
            Allows to run ONNX Runtime optimizations directly during the export. Some of these optimizations are specific to
            ONNX Runtime, and the resulting ONNX will not be usable with other runtime as OpenVINO or TensorRT.
            Available options: `"O1", "O2", "O3", "O4"`. Reference: [`~optimum.onnxruntime.AutoOptimizationConfig`]
        monolith (`bool`, defaults to `False`):
            Forces to export the model as a single ONNX file.
        no_post_process (`bool`, defaults to `False`):
            Allows to disable any post-processing done by default on the exported ONNX models.
        framework (`Optional[str]`, defaults to `None`):
            The framework to use for the ONNX export (`"pt"` or `"tf"`). If not provided, will attempt to automatically detect
            the framework for the checkpoint.
        atol (`Optional[float]`, defaults to `None`):
            If specified, the absolute difference tolerance when validating the model. Otherwise, the default atol for the model will be used.
        cache_dir (`Optional[str]`, defaults to `None`):
            Path indicating where to store cache. The default Hugging Face cache path will be used by default.
        trust_remote_code (`bool`, defaults to `False`):
            Allows to use custom code for the modeling hosted in the model repository. This option should only be set for repositories
            you trust and in which you have read the code, as it will execute on your local machine arbitrary code present in the
            model repository.
        pad_token_id (`Optional[int]`, defaults to `None`):
            This is needed by some models, for some tasks. If not provided, will attempt to use the tokenizer to guess it.
        subfolder (`str`, defaults to `""`):
            In case the relevant files are located inside a subfolder of the model repo either locally or on huggingface.co, you can
            specify the folder name here.
        revision (`str`, defaults to `"main"`):
            Revision is the specific model version to use. It can be a branch name, a tag name, or a commit id.
        force_download (`bool`, defaults to `False`):
            Whether or not to force the (re-)download of the model weights and configuration files, overriding the
            cached versions if they exist.
        local_files_only (`Optional[bool]`, defaults to `False`):
            Whether or not to only look at local files (i.e., do not try to download the model).
        use_auth_token (`Optional[str]`, defaults to `None`):
            The token to use as HTTP bearer authorization for remote files. If `True`, will use the token generated
            when running `transformers-cli login` (stored in `~/.huggingface`).
        model_kwargs (`Optional[Dict[str, Any]]`, defaults to `None`):
            Experimental usage: keyword arguments to pass to the model during
            the export. This argument should be used along the `custom_onnx_configs` argument
            in case, for example, the model inputs/outputs are changed (for example, if
            `model_kwargs={"output_attentions": True}` is passed).
        custom_onnx_configs (`Optional[Dict[str, OnnxConfig]]`, defaults to `None`):
            Experimental usage: override the default ONNX config used for the given model. This argument may be useful for advanced users that desire a finer-grained control on the export. An example is available [here](https://huggingface.co/docs/optimum/main/en/exporters/onnx/usage_guides/export_a_model).
        fn_get_submodels (`Optional[Callable]`, defaults to `None`):
            Experimental usage: Override the default submodels that are used at the export. This is
            especially useful when exporting a custom architecture that needs to split the ONNX (e.g. encoder-decoder). If unspecified with custom models, optimum will try to use the default submodels used for the given task, with no guarantee of success.
        use_subprocess (`bool`):
            Do the ONNX exported model validation in subprocesses. This is especially useful when
            exporting on CUDA device, where ORT does not release memory at inference session
            destruction. When set to `True`, the `main_export` call should be guarded in
            `if __name__ == "__main__":` block.
        _variant (`str`, defaults to `default`):
            Specify the variant of the ONNX export to use.
        **kwargs_shapes (`Dict`):
            Shapes to use during inference. This argument allows to override the default shapes used during the ONNX export.

    Example usage:
    ```python
    >>> from optimum.exporters.onnx import main_export

    >>> main_export("gpt2", output="gpt2_onnx/")
    ```
    """
    if optimize == "O4" and device != "cuda":
        raise ValueError(
            "Requested O4 optimization, but this optimization requires to do the export on GPU."
            " Please pass the argument `--device cuda`."
        )

    if (framework == "tf" and fp16 is True) or not is_torch_available():
        raise ValueError("The --fp16 option is supported only for PyTorch.")

    if fp16 is True and device == "cpu":
        raise ValueError(
            "FP16 export is supported only when exporting on GPU. Please pass the option `--device cuda`."
        )
        float_dtype = "fp16"
    else:
        float_dtype = "fp32"

    output = Path(output)
    if not output.exists():
        output.mkdir(parents=True)

    if for_ort:
        logger.warning(
            "The option --for-ort was passed, but its behavior is now the default in the ONNX exporter"
            " and passing it is not required anymore."
        )

    original_task = task
    task = TasksManager.map_from_synonym(task)

    framework = TasksManager.determine_framework(model_name_or_path, subfolder=subfolder, framework=framework)

    # get the shapes to be used to generate dummy inputs
    input_shapes = {}
    for input_name in DEFAULT_DUMMY_SHAPES.keys():
        input_shapes[input_name] = (
            kwargs_shapes[input_name] if input_name in kwargs_shapes else DEFAULT_DUMMY_SHAPES[input_name]
        )

    torch_dtype = None if fp16 is False else torch.float16

    if task == "auto":
        try:
            task = TasksManager.infer_task_from_model(model_name_or_path)
        except KeyError as e:
            raise KeyError(
                f"The task could not be automatically inferred. Please provide the argument --task with the relevant task from {', '.join(TasksManager.get_all_tasks())}. Detailed error: {e}"
            )
        except RequestsConnectionError as e:
            raise RequestsConnectionError(
                f"The task could not be automatically inferred as this is available only for models hosted on the Hugging Face Hub. Please provide the argument --task with the relevant task from {', '.join(TasksManager.get_all_tasks())}. Detailed error: {e}"
            )

    if model is None:
        model = TasksManager.get_model_from_task(
            task,
            model_name_or_path,
            subfolder=subfolder,
            revision=revision,
            cache_dir=cache_dir,
            use_auth_token=use_auth_token,
            local_files_only=local_files_only,
            force_download=force_download,
            trust_remote_code=trust_remote_code,
            framework=framework,
            torch_dtype=torch_dtype,
            device=device,
        )

    custom_architecture = False
    is_stable_diffusion = "stable-diffusion" in task
    model_type = "stable-diffusion" if is_stable_diffusion else model.config.model_type.replace("_", "-")

    if not is_stable_diffusion:
        if model_type in TasksManager._UNSUPPORTED_CLI_MODEL_TYPE:
            raise ValueError(
                f"{model_type} is not supported yet. Only {TasksManager._SUPPORTED_CLI_MODEL_TYPE} are supported. "
                f"If you want to support {model_type} please propose a PR or open up an issue."
            )
        if model.config.model_type.replace("-", "_") not in TasksManager.get_supported_model_type_for_task(
            task, exporter="onnx"
        ):
            custom_architecture = True

    # TODO: support onnx_config.py in the model repo
    if custom_architecture and custom_onnx_configs is None:
        raise ValueError(
            f"Trying to export a {model.config.model_type.replace('-', '_')} model, that is a custom or unsupported architecture for the task {task}, but no custom onnx configuration was passed as `custom_onnx_configs`. Please refer to https://huggingface.co/docs/optimum/main/en/exporters/onnx/usage_guides/export_a_model#custom-export-of-transformers-models for an example on how to export custom models. For the task {task}, the Optimum ONNX exporter supports natively the architectures: {TasksManager.get_supported_model_type_for_task(task, exporter='onnx')}."
        )

    if custom_architecture and original_task == "auto":
        raise ValueError(
            f'Automatic task detection is not supported with custom architectures. Please specify the `task` argument. Suggestion: task="{task}" (or task="{task}-with-past" if the model is decoder-based and supports KV cache)'
        )

    if (
        not custom_architecture
        and not is_stable_diffusion
        and task + "-with-past" in TasksManager.get_supported_tasks_for_model_type(model_type, "onnx")
    ):
        if original_task == "auto":  # Make -with-past the default if --task was not explicitely specified
            task = task + "-with-past"
        else:
            logger.info(
                f"The task `{task}` was manually specified, and past key values will not be reused in the decoding."
                f" if needed, please pass `--task {task}-with-past` to export using the past key values."
            )

    if task.endswith("-with-past") and monolith is True:
        task_non_past = task.replace("-with-past", "")
        raise ValueError(
            f"The task {task} is not compatible with the --monolith argument. Please either use"
            f" `--task {task_non_past} --monolith`, or `--task {task}` without the monolith argument."
        )

    if original_task == "auto":
        synonyms_for_task = sorted(TasksManager.synonyms_for_task(task))
        if synonyms_for_task:
            synonyms_for_task = ", ".join(synonyms_for_task)
            possible_synonyms = f" (possible synonyms are: {synonyms_for_task})"
        else:
            possible_synonyms = ""
        logger.info(f"Automatic task detection to {task}{possible_synonyms}.")

    # The preprocessors are loaded as they may be useful to export the model. Notably, some of the static input shapes may be stored in the
    # preprocessors config.
    preprocessors = maybe_load_preprocessors(
        model_name_or_path, subfolder=subfolder, trust_remote_code=trust_remote_code
    )
    onnx_config, models_and_onnx_configs = _get_submodels_and_onnx_configs(
        model=model,
        task=task,
        monolith=monolith,
        custom_onnx_configs=custom_onnx_configs if custom_onnx_configs is not None else {},
        custom_architecture=custom_architecture,
        float_dtype=float_dtype,
        fn_get_submodels=fn_get_submodels,
        preprocessors=preprocessors,
        _variant=_variant,
    )

    if not is_stable_diffusion:
        needs_pad_token_id = (
            isinstance(onnx_config, OnnxConfigWithPast)
            and getattr(model.config, "pad_token_id", None) is None
            and task in ["text-classification"]
        )
        if needs_pad_token_id:
            if pad_token_id is not None:
                model.config.pad_token_id = pad_token_id
            else:
                try:
                    tok = AutoTokenizer.from_pretrained(model_name_or_path)
                    model.config.pad_token_id = tok.pad_token_id
                except Exception:
                    raise ValueError(
                        "Could not infer the pad token id, which is needed in this case, please provide it with the --pad_token_id argument"
                    )

        # Ensure the requested opset is sufficient
        if opset is None:
            opset = onnx_config.DEFAULT_ONNX_OPSET

        if opset < onnx_config.DEFAULT_ONNX_OPSET:
            raise ValueError(
                f"Opset {opset} is not sufficient to export {model_type}. "
                f"At least {onnx_config.DEFAULT_ONNX_OPSET} is required."
            )
        if atol is None:
            atol = onnx_config.ATOL_FOR_VALIDATION
            if isinstance(atol, dict):
                atol = atol[task.replace("-with-past", "")]

        # Saving the model config and preprocessor as this is needed sometimes.
        model.config.save_pretrained(output)
        generation_config = getattr(model, "generation_config", None)
        if generation_config is not None:
            generation_config.save_pretrained(output)
        maybe_save_preprocessors(model_name_or_path, output)

        if model.config.is_encoder_decoder and task.startswith("text-generation"):
            raise ValueError(
                f"model.config.is_encoder_decoder is True and task is `{task}`, which are incompatible. If the task was auto-inferred, please fill a bug report"
                f"at https://github.com/huggingface/optimum, if --task was explicitely passed, make sure you selected the right task for the model,"
                f" referring to `optimum.exporters.tasks.TaskManager`'s `_TASKS_TO_AUTOMODELS`."
            )

        onnx_files_subpaths = [key + ".onnx" for key in models_and_onnx_configs.keys()]
    else:
        # save the subcomponent configuration
        for model_name in models_and_onnx_configs:
            subcomponent = models_and_onnx_configs[model_name][0]
            if hasattr(subcomponent, "save_config"):
                subcomponent.save_config(output / model_name)
            elif hasattr(subcomponent, "config") and hasattr(subcomponent.config, "save_pretrained"):
                subcomponent.config.save_pretrained(output / model_name)

        onnx_files_subpaths = [os.path.join(name_dir, ONNX_WEIGHTS_NAME) for name_dir in models_and_onnx_configs]

        # Saving the additional components needed to perform inference.
        model.scheduler.save_pretrained(output.joinpath("scheduler"))

        feature_extractor = getattr(model, "feature_extractor", None)
        if feature_extractor is not None:
            feature_extractor.save_pretrained(output.joinpath("feature_extractor"))

        tokenizer = getattr(model, "tokenizer", None)
        if tokenizer is not None:
            tokenizer.save_pretrained(output.joinpath("tokenizer"))

        tokenizer_2 = getattr(model, "tokenizer_2", None)
        if tokenizer_2 is not None:
            tokenizer_2.save_pretrained(output.joinpath("tokenizer_2"))

        model.save_config(output)

    _, onnx_outputs = export_models(
        models_and_onnx_configs=models_and_onnx_configs,
        opset=opset,
        output_dir=output,
        output_names=onnx_files_subpaths,
        input_shapes=input_shapes,
        device=device,
        dtype="fp16" if fp16 is True else None,
        model_kwargs=model_kwargs,
    )

    # for the post processing later we don't wanna keep models
    for key in models_and_onnx_configs.keys():
        models_and_onnx_configs[key] = ("dummy_model", models_and_onnx_configs[key][1])

    return onnx_config, models_and_onnx_configs

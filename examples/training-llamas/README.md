# Optimum-Benchmark x LLaMAs x PEFT

A set of benchmarks on Meta's LLaMA2's training.

Just run these commands from this directory:

```bash
optimum-benchmark --config-dir configs/ --config-name llama_peft+gptq --multirun
optimum-benchmark --config-dir configs/ --config-name llama_peft+bnb --multirun
```

This will create a folder called `experiments` with the results of the benchmarks with a training `batch_size` ranging from 1 to 16. Then run

```bash
python report.py -e experiments
```

Which will create some quick reporting artifacts like a `full_report.csv`, `short_report.csv`, `throughput_plot.png` and `rich_table.svg`.

## Results

### On A100-80GB

<p align="center">
<img src="artifacts/A100-80GB/throughput_plot.png" alt="throughput_plot" width="60%"/>
</p>

<p align="center">
<img src="artifacts/A100-80GB/rich_table.svg" alt="rich_table" width="90%"/>
</p>

### On RTX4090-24GB

<p align="center">
<img src="artifacts/RTX4090-24GB/throughput_plot.png" alt="throughput_plot" width="60%"/>
</p>

<p align="center">
<img src="artifacts/RTX4090-24GB/rich_table.svg" alt="rich_table" width="90%"/>
</p>
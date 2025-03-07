from argparse import ArgumentParser
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from flatten_dict import flatten
from omegaconf import OmegaConf
from pandas import DataFrame
from rich.console import Console
from rich.table import Table
from rich.terminal_theme import MONOKAI


def gather_inference_report(root_folder: Path) -> DataFrame:
    # key is path to inference file as string, value is dataframe
    inference_dfs = {
        f.parent.absolute().as_posix(): pd.read_csv(f) for f in root_folder.glob("**/inference_results.csv")
    }

    # key is path to config file as string, value is flattened dict
    config_dfs = {
        f.parent.absolute()
        .as_posix(): pd.DataFrame.from_dict(flatten(OmegaConf.load(f), reducer="dot"), orient="index")
        .T
        for f in root_folder.glob("**/hydra_config.yaml")
        if f.parent.absolute().as_posix() in inference_dfs.keys()
    }

    if len(inference_dfs) == 0 or len(config_dfs) == 0:
        raise ValueError(f"No results found in {root_folder}")

    # Merge inference and config dataframes
    inference_reports = [
        config_dfs[name].merge(inference_dfs[name], left_index=True, right_index=True) for name in inference_dfs.keys()
    ]

    # Concatenate all reports
    inference_report = pd.concat(inference_reports, axis=0, ignore_index=True)
    inference_report.set_index("experiment_name", inplace=True)
    return inference_report


def style_element(element, style=""):
    if style:
        return f"[{style}]{element}[/{style}]"
    else:
        return element


def format_element(element, style=""):
    if isinstance(element, float):
        if element != element:  # nan
            formated_element = ""
        elif abs(element) >= 1:
            formated_element = f"{element:.2f}"
        elif abs(element) > 1e-6:
            formated_element = f"{element:.2e}"
        else:
            formated_element = f"{element}"
    elif element is None:
        formated_element = ""
    elif isinstance(element, bool):
        if element:
            formated_element = style_element("✔", style="green")
        else:
            formated_element = style_element("✘", style="red")
    else:
        formated_element = str(element)

    return style_element(formated_element, style=style)


def format_row(row, style=""):
    formated_row = []
    for element in row:
        formated_row.append(format_element(element, style=style))
    return formated_row


def get_inference_rich_table(inference_report, with_baseline=False, with_generate=False, title=""):
    perf_columns = [
        "forward.latency(s)",
        "forward.throughput(samples/s)",
    ] + (
        [
            "forward.peak_memory(MB)",
        ]
        if "forward.peak_memory(MB)" in inference_report.columns
        else []
    )

    if with_baseline:
        perf_columns.append("forward.speedup(%)")

    if with_generate:
        perf_columns += ["generate.latency(s)", "generate.throughput(tokens/s)"]
        if with_baseline:
            perf_columns.append("generate.speedup(%)")

    additional_columns = [
        col
        for col in inference_report.columns
        if inference_report[col].nunique() > 1 and "backend" in col and "_target_" not in col and "version" not in col
    ]

    # display interesting columns in multilevel hierarchy
    display_report = inference_report[additional_columns + perf_columns]
    display_report.columns = pd.MultiIndex.from_tuples([tuple(col.split(".")) for col in display_report.columns])

    # create rich table
    rich_table = Table(show_header=True, title=title, show_lines=True)
    # we add a column for the index
    rich_table.add_column("Experiment Name", justify="left", header_style="")
    # then we add the rest of the columns
    for level in range(display_report.columns.nlevels):
        columns = display_report.columns.get_level_values(level).to_list()
        for i in range(len(columns)):
            if columns[i] != columns[i]:  # nan
                columns[i] = ""

        if level < display_report.columns.nlevels - 1:
            for col in columns:
                rich_table.add_column(col, header_style="")
            pass
        else:
            rich_table.add_row(
                "",
                *columns,
                end_section=True,
            )

    # we populate the table with values
    for i, row in enumerate(display_report.itertuples(index=True)):
        if with_baseline and i == display_report.shape[0] - 1:
            table_row = format_row(row, style="yellow")
        else:
            table_row = format_row(row)

        rich_table.add_row(*table_row)

    return rich_table


def get_inference_plots(report, with_baseline=False, with_generate=False, subtitle=""):
    # create bar charts seperately
    fig1, ax1 = plt.subplots(figsize=(20, 10))
    fig2, ax2 = plt.subplots(figsize=(20, 10))

    sns.barplot(
        x=report.index,
        y=report["forward.throughput(samples/s)"],
        ax=ax1,
        width=0.5,
    )
    ax1.set_xticklabels(ax1.get_xticklabels(), rotation=45, horizontalalignment="right")
    ax1.set_xlabel("Experiment")
    ax1.set_ylabel("Forward Throughput (samples/s)")
    ax1.set_title("Forward Throughput by Experiment" + "\n" + subtitle)

    if with_generate:
        fig2, ax2 = plt.subplots(figsize=(20, 10))
        sns.barplot(
            x=report.index,
            y=report["generate.throughput(tokens/s)"],
            ax=ax2,
            width=0.5,
        )
        ax2.set_xticklabels(ax2.get_xticklabels(), rotation=45, horizontalalignment="right")
        ax2.set_xlabel("Experiment")
        ax2.set_ylabel("Generate Throughput (tokens/s)")
        ax2.set_title("Generate Throughput by Experiment" + "\n" + subtitle)

    if with_baseline:
        # add speedup text on top of each bar
        baselineforward_throughput = report["forward.throughput(samples/s)"].iloc[-1]
        for p in ax1.patches:
            speedup = (p.get_height() / baselineforward_throughput - 1) * 100
            ax1.annotate(
                f"{'+' if speedup>0 else '-'}{abs(speedup):.2f}%",
                (p.get_x() + p.get_width() / 2, 1.02 * p.get_height()),
                ha="center",
                va="center",
            )
        ax1.set_title("Forward Throughput and Speedup by Experiment" + "\n" + subtitle)

        if with_generate:
            # add speedup text on top of each bar
            baseline_generate_throughput = report["generate.throughput(tokens/s)"].iloc[-1]
            for p in ax2.patches:
                speedup = (p.get_height() / baseline_generate_throughput - 1) * 100
                ax2.annotate(
                    f"{'+' if speedup>0 else '-'}{abs(speedup):.2f}%",
                    (p.get_x() + p.get_width() / 2, 1.02 * p.get_height()),
                    ha="center",
                    va="center",
                )
            ax2.set_title("Generate Throughput and Speedup by Experiment" + "\n" + subtitle)

    return fig1, fig2


def compute_speedup(report, with_generate=False):
    # compute speedup for each experiment compared to baseline
    report["forward.speedup(%)"] = (
        report["forward.throughput(samples/s)"] / report["forward.throughput(samples/s)"].iloc[-1] - 1
    ) * 100

    if with_generate:
        report["generate.speedup(%)"] = (
            report["generate.throughput(tokens/s)"] / report["generate.throughput(tokens/s)"].iloc[-1] - 1
        ) * 100

    return report


def generate_report():
    parser = ArgumentParser()
    parser.add_argument(
        "--experiments",
        "-e",
        nargs="*",
        type=Path,
        required=True,
        help="The folder containing the results of experiments.",
    )
    parser.add_argument(
        "--baseline",
        "-b",
        type=Path,
        required=False,
        help="The folders containing the results of baseline.",
    )
    parser.add_argument(
        "--report-name",
        "-n",
        type=str,
        required=False,
        help="The name of the report.",
    )

    args = parser.parse_args()

    experiments_folders = args.experiments
    baseline_folder = args.baseline
    report_name = args.report_name

    # gather experiments reports
    inference_experiments = [gather_inference_report(experiment) for experiment in experiments_folders]
    inference_report = pd.concat(inference_experiments, axis=0)

    # sort by forward throughput
    inference_report.sort_values(by="forward.throughput(samples/s)", ascending=False, inplace=True)

    # some flags
    with_baseline = baseline_folder is not None
    with_generate = "generate.throughput(tokens/s)" in inference_report.columns

    if with_baseline:
        # gather baseline report
        inference_baseline = gather_inference_report(baseline_folder)
        assert inference_baseline.shape[0] == 1, "baseline folder should contain only one experiment"
        # add baseline to experiment
        inference_report = pd.concat([inference_report, inference_baseline], axis=0)
        # compute speedup compared to baseline
        inference_report = compute_speedup(inference_report, with_generate)

    # create reporting directory and title using the filters
    if report_name is None:
        report_name = "Inference Report"
        reporting_directory = "reports/inferece_report"
    else:
        reporting_directory = f"reports/{report_name}"

    Path(reporting_directory).mkdir(exist_ok=True, parents=True)

    # rich table
    rich_table = get_inference_rich_table(inference_report, with_baseline, with_generate, report_name)
    console = Console(record=True)
    console.print(rich_table, justify="left", no_wrap=True)
    console.save_svg(f"{reporting_directory}/rich_table.svg", theme=MONOKAI)

    # plots
    forward_fig, generate_fig = get_inference_plots(inference_report, with_baseline, with_generate, report_name)
    forward_fig.tight_layout()
    forward_fig.savefig(f"{reporting_directory}/forward_throughput.png")

    if generate_fig is not None:
        generate_fig.tight_layout()
        generate_fig.savefig(f"{reporting_directory}/generate_throughput.png")

    # csv
    inference_report.to_csv(f"{reporting_directory}/inference_report.csv", index=True)

from os import scandir
from pathlib import Path


def fast_scandir(path: Path) -> list:
    subfolders = [entry.path for entry in scandir(path) if entry.is_dir()]
    for subfolder in subfolders:
        subfolders.extend(fast_scandir(subfolder))
    return subfolders


def initialise(output_path: Path = Path.cwd().joinpath("output_files")) -> None:
    cwd = Path.cwd()
    required_dirs = (output_path.joinpath("netmc"), cwd.joinpath("batches", "netmc"),
                     output_path.joinpath("triangle_raft"), cwd.joinpath("batches", "triangle_raft"),
                     output_path.joinpath("netmc_pores"), cwd.joinpath("batches", "netmc_pores"))
    required_files = (cwd.joinpath("batch_history.txt"),)
    for directory in required_dirs:
        if not directory.exists():
            directory.mkdir(parents=True)
    for file in required_files:
        if not file.exists():
            file.touch()

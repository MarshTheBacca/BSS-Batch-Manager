from pathlib import Path


def fast_scandir(path: Path) -> list[Path]:
    """
    Recursively scan a directory for all subfolders

    Args:
        path: Path: The path to scan
    Returns:
        list[Path]: A list of all subfolders
    """
    subfolders = [path for path in Path.iterdir(path) if path.is_dir()]
    for subfolder in subfolders:
        subfolders.extend(fast_scandir(subfolder))
    return subfolders

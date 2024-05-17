import shutil
from pathlib import Path


def merge_jobs(paths: set[Path]) -> None:
    all_batch_paths = {sub_path for path in paths for sub_path in path.iterdir() if sub_path.is_dir()}
    sub_batches = {sub_path for sub_path in all_batch_paths if sub_path.name.endswith("sub_batch")}
    for sub_batch in sub_batches:
        parent_batch_name = sub_batch.name[:-10]
        parent_batch_path = next((path for path in all_batch_paths if path.name == parent_batch_name), None)
        if parent_batch_path is None:
            print(f"Warning: Sub batch {sub_batch.name} has no parent batch")
            continue
        print(f"Merging sub batch {sub_batch.name} into parent batch {parent_batch_name}")
        for job in sub_batch.joinpath("run_1", "jobs").iterdir():
            shutil.move(job, parent_batch_path.joinpath("run_1", "jobs", job.name))
        shutil.rmtree(sub_batch)


def main() -> None:
    output_files_path = Path(__file__).parent.joinpath("output_files")
    secondary_output_files_path = Path("/media/marshthebacca/Marshalls_HDD_1/BSS-Batch-Manager-Secondary")
    merge_jobs({output_files_path, secondary_output_files_path})


if __name__ == "__main__":
    main()

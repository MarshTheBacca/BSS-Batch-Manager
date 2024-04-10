from __future__ import annotations

from dataclasses import dataclass, field
from datetime import timezone
from pathlib import Path

from tabulate import tabulate

from .array_utils import import_2d
from .batch import Batch
from .ssh_utils import LogInException, ssh_login_silent
from .validation_utils import get_valid_int


@dataclass
class BatchData:
    batches: list[Batch] = field(default_factory=list)
    deleted_batches: list[Batch] = field(default_factory=list)
    log_path: Path = Path("batch_log.csv")

    @staticmethod
    def from_files(batch_log_path: Path, batches_path: Path) -> BatchData:
        batch_log = import_2d(batch_log_path)
        logged_batches = {}
        for log in batch_log:
            if log[1] not in logged_batches:
                logged_batches[log[1]] = [log[0]]
            else:
                logged_batches[log[1]].append(log[0])
        current_batches = [batch.name[:-4] for batch in batches_path.iterdir() if batch.name.endswith(".zip")]
        batch_data = BatchData(log_path=batch_log_path)
        for batch_name, run_times in logged_batches.items():
            if batch_name not in current_batches:
                batch_data.add_batch(Batch(batch_name, batches_path.joinpath(f"{batch_name}.zip"), run_times, True))
            else:
                batch_data.add_batch(Batch(batch_name, batches_path.joinpath(f"{batch_name}.zip"), run_times, False))
        for batch in current_batches:
            if batch not in [batch.name for batch in batch_data.batches]:
                batch_data.add_batch(Batch(batch, batches_path.joinpath(f"{batch}.zip"), [], False))
        return batch_data

    def refresh(self, batches_path: Path) -> None:
        current_batches = [batch.name[:-4] for batch in batches_path.iterdir() if batch.name.endswith(".zip")]
        for batch in current_batches:
            if batch not in [batch.name for batch in self.batches]:
                self.add_batch(Batch(batch, batches_path.joinpath(f"{batch}.zip"), [], False))

    def add_batch(self, batch: Batch) -> None:
        if not batch.deleted:
            self.batches.append(batch)
            return
        self.deleted_batches.append(batch)

    def table_print(self, t_zone: timezone = timezone.utc, include_deleted: bool = False) -> None:
        if include_deleted:
            batches = self.batches + self.deleted_batches
        else:
            batches = self.batches
        array = [[i] + list(batch.convert_to_array(t_zone)) for i, batch in enumerate(batches, start=1)]
        # Sort by most recent run
        LAST_RUN_INDEX = 4
        array.sort(key=lambda x: x[LAST_RUN_INDEX], reverse=True)
        print(tabulate(array, headers=["#", "Batch Name", "Number of Jobs", "Number of Runs", "Last Ran"], tablefmt="fancy_grid"))

    def submit_batch(self, output_path: Path, submit_script_path: Path, username: str) -> None:
        if not self.batches:
            print("There are no batches to submit!")
            return
        exit_num = len(self.batches) + 1
        self.table_print()
        option = get_valid_int(f"Which batch would you like to submit? ({exit_num} to exit)\n", 1, exit_num)
        if option == exit_num:
            return
        try:
            ssh = ssh_login_silent(username=username)
        except LogInException as e:
            print(e)
            return
        ssh.close()
        self.batches[option - 1].submit(username, output_path, submit_script_path)
        self.log_batch(self.batches[option - 1])

    def log_batch(self, batch: Batch) -> None:
        with open(self.log_path, "a") as log_file:
            log_file.write(f"{batch.get_last_ran.strftime("%Y %a %d %b %H:%M:%S %Z")},{batch.name}\n")

    def __repr__(self) -> str:
        return_string = "BatchData object with the following batches:\nCurrent Batches:\n"
        for batch in self.batches:
            return_string += f"{batch}\n"
        return_string += "Deleted Batches:\n"
        for batch in self.deleted_batches:
            return_string += f"{batch}\n"
        return return_string

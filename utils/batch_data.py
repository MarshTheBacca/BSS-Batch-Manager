from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from tabulate import tabulate
from tzlocal import get_localzone

from .array_utils import import_2d
from .batch import Batch
from .ssh_utils import LogInException, ssh_login_silent
from .validation_utils import confirm, get_valid_int

LAST_RUN_INDEX = 3
LOCAL_TZ = get_localzone()


@dataclass
class BatchData:
    batches: list[Batch] = field(default_factory=list)
    deleted_batches: list[Batch] = field(default_factory=list)
    log_path: Path = Path("batch_log.csv")

    @staticmethod
    def from_files(batch_log_path: Path, batches_path: Path) -> BatchData:
        batch_log = import_2d(batch_log_path)
        batch_log = [[datetime.strptime(log[0], "%Y %a %d %b %H:%M:%S %Z").replace(tzinfo=timezone.utc), log[1]] for log in batch_log]
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

    def table_print(self, t_zone: timezone = LOCAL_TZ, include_deleted: bool = False) -> None:
        if include_deleted:
            batches = self.batches + self.deleted_batches
        else:
            batches = self.batches
        batches.sort(reverse=True)
        array = [batch.convert_to_array(t_zone) for batch in batches]
        # Add numbers
        array = [[i] + list(row) for i, row in enumerate(array, start=1)]
        tz_name = datetime.now(t_zone).strftime("%Z")
        print(tabulate(array, headers=["#", "Batch Name", "Number of Jobs", "Number of Runs", f"Last Ran ({tz_name})"], tablefmt="fancy_grid"))

    def add_batch(self, batch: Batch) -> None:
        if not batch.deleted:
            self.batches.append(batch)
            return
        self.deleted_batches.append(batch)

    def delete_batch(self) -> None:
        if not self.batches:
            print("There are no batches to delete!")
            return
        self.table_print()
        option = get_valid_int("Which batch would you like to delete?\n", 1, len(self.batches))
        if option is None:
            return
        batch = self.batches.pop(option - 1)
        if not confirm(f"Are you sure you want to delete {batch.name}? (y/n)\n"):
            return
        batch.delete()
        self.deleted_batches.append(batch)
        print(f"Batch {batch.name} deleted successfully!")

    def submit_batch(self, output_path: Path, submit_script_path: Path, username: str, hostname: str) -> None:
        while True:
            if not self.batches:
                print("There are no batches to submit!")
                return
            exit_num = len(self.batches) + 1
            self.table_print()
            option = get_valid_int(f"Which batch would you like to submit? ({exit_num} to exit)\n", 1, exit_num)
            if option == exit_num:
                return
            selected_batch: Batch = self.batches[option - 1]
            if not (confirm(f"Are you sure you want to submit {selected_batch.name} to {hostname}? (y/n)\n")):
                continue
            try:
                ssh = ssh_login_silent(username=username, hostname=hostname)
            except LogInException as e:
                print(e)
                return
            ssh.close()
            selected_batch.submit(username, hostname, output_path, submit_script_path)
            self.log_batch(self.batches[option - 1])
            print(f"Batch {self.batches[option - 1].name} submitted successfully!")

    def log_batch(self, batch: Batch) -> None:
        with open(self.log_path, "a") as log_file:
            log_file.write(f"{batch.get_last_ran.strftime('%Y %a %d %b %H:%M:%S %Z')},{batch.name}\n")

    def __repr__(self) -> str:
        return_string = "BatchData object with the following batches:\nCurrent Batches:\n"
        for batch in self.batches:
            return_string += f"{batch}\n"
        return_string += "Deleted Batches:\n"
        for batch in self.deleted_batches:
            return_string += f"{batch}\n"
        return return_string

from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import UTC, datetime, timezone
from typing import TYPE_CHECKING
from zipfile import ZipFile

from .other_utils import background_process

if TYPE_CHECKING:
    from pathlib import Path


class EmptyBatchError(Exception):
    """Thrown when a batch is empty."""


@dataclass
class Batch:
    name: str
    path: Path
    run_times: list[datetime]
    deleted: bool = False

    def __post_init__(self) -> None:
        # Sort dates submitted from oldest to newest
        self.run_times = sorted(self.run_times)
        try:
            with ZipFile(self.path, "r") as batch_zip:
                self.jobs: set[str] = set(sub_path.split("/")[1] for sub_path in batch_zip.namelist() if sub_path.startswith("jobs/") and sub_path.split("/")[1])
        except FileNotFoundError:
            if not self.deleted:
                raise EmptyBatchError(f"Batch {self.name} does not exist")
            self.jobs = set()

        self.num_jobs: int = len(self.jobs)
        self.num_runs: int = len(self.run_times)

    def submit(self, username: str, hostname: str, output_path: Path, submit_script_path: Path) -> None:
        """Submits the batch to host by launching a background task.

        The task runs the submit script and checks every 5 seconds if the batch has
        been completed, and then returns the output files as a zip file

        Args:
            username (str): The username for the remote host
            hostname (str): The server host name, eg, my.host.com
            submit_script_path (Path): The path to the submit script
            output_path (Path): The path to the directory to save the output files
        """
        background_process([sys.executable, submit_script_path, "-n", self.name, "-x", str(self.num_runs), "-p", self.path, "-o", output_path, "-u", username, "-z", hostname])
        self.num_runs += 1
        self.run_times.append(datetime.now(UTC))

    def delete(self) -> None:
        """Deletes the batch by setting the deleted attribute to True"""
        self.path.unlink()
        self.deleted = True

    def convert_to_array(self, t_zone: timezone = UTC) -> tuple[str, int, int, str]:
        """Converts the Batch object to an array for use in a table.

        Args:
            t_zone (timezone): The timezone to convert the last ran time to
        Returns:
            The array representation of the Batch object
        """
        if self.get_last_ran is None:
            last_ran_string = "Never Ran"
        else:
            last_ran_string = self.get_last_ran.astimezone(t_zone).strftime("%Y %a %d %b %H:%M:%S")
        return (self.name, self.num_jobs, self.num_runs, last_ran_string)

    @property
    def get_last_ran(self) -> datetime | None:
        """Returns the last ran time of the Batch object.

        Returns:
            The last time the batch was run, or None if it has never been run
        """
        try:
            return self.run_times[-1]
        except IndexError:
            return None

    def __repr__(self) -> str:
        """Returns a string representation of the Batch object."""
        return f"Batch {self.name} with {self.num_jobs} jobs and ran {self.num_runs} times at: {self.run_times}"

    def __lt__(self, other: Batch) -> bool:
        """Compares the last ran times of two Batch objects.

        Args:
            other (Batch): The other Batch object to compare to
        Returns:
            bool: True if the last ran time of this Batch is less than the other Batch,
            False otherwise
            NotImplemented: If the other object is not a Batch object
        """
        try:
            if isinstance(other, Batch):
                if self.get_last_ran is None:
                    return True
                if other.get_last_ran is None:
                    return False
                return self.get_last_ran < other.get_last_ran
        except TypeError:
            print(f"Trying to compare: {self} and {other}")
            raise
        else:
            return NotImplemented

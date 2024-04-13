from __future__ import annotations

import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from zipfile import ZipFile

from .other_utils import background_process


class EmptyBatchError(Exception):
    pass


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
                exclude_folders = ("initial_lammps_files", "initial_network")
                self.jobs: set[str] = set(sub_path.split('/')[0] for sub_path in batch_zip.namelist()
                                          if '/' in sub_path and sub_path.split('/')[0] not in exclude_folders)
        except FileNotFoundError:
            if not self.deleted:
                raise EmptyBatchError(f"Batch {self.name} does not exist")
            self.jobs = []

        self.num_jobs: int = len(self.jobs)
        self.num_runs: int = len(self.run_times)

    def submit(self, username: str, output_path: Path, submit_script_path: Path) -> None:
        """
        Submits the batch to Coulson by launching a background task that runs the submit script
        and checks every 5 seconds if the batch has been completed, and then returns
        the output files as a zip file

        Args:
            username (str): The username for the remote host (Coulson)
            submit_script_path (Path): The path to the submit script
            output_path (Path): The path to the directory to save the output files
        """
        background_process([sys.executable, submit_script_path,
                            "-n", self.name,
                            "-x", str(self.num_runs),
                            "-p", self.path,
                            "-o", output_path,
                            "-u", username])
        self.num_runs += 1
        self.run_times.append(datetime.now(timezone.utc))

    def delete(self) -> None:
        """
        Deletes the batch by setting the deleted attribute to True
        """
        self.path.unlink()
        self.deleted = True

    def convert_to_array(self, t_zone: timezone = timezone.utc) -> tuple[str, int, int, str]:
        """
        Converts the Batch object to an array for use in a table

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

    @ property
    def get_last_ran(self) -> Optional[datetime]:
        """
        Returns the last ran time of the Batch object

        Returns:
            The last time the batch was run, or None if it has never been run
        """
        try:
            return self.run_times[-1]
        except IndexError:
            return None

    def __repr__(self) -> str:
        """
        Returns a string representation of the Batch object
        """
        return f"Batch {self.name} with {self.num_jobs} jobs and ran {self.num_runs} times at: {self.run_times}"

    def __lt__(self, other: Batch) -> bool:
        """
        Compares the last ran times of two Batch objects

        Args:
            other (Batch): The other Batch object to compare to
        Returns:
            bool: True if the last ran time of this Batch is less than the other Batch, False otherwise
            NotImplemented: If the other object is not a Batch object
        """
        try:
            if isinstance(other, Batch):
                if self.get_last_ran is None:
                    return True
                elif other.get_last_ran is None:
                    return False
                else:
                    return self.get_last_ran < other.get_last_ran
            else:
                return NotImplemented
        except TypeError as e:
            print(f"Trying to compare: {self} and {other}")
            raise TypeError(e)

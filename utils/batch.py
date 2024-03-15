from __future__ import annotations
from zipfile import ZipFile
from datetime import datetime, timezone
from .other_utils import background_process
from dataclasses import dataclass
from pathlib import Path
from sys import executable
from typing import Optional, Tuple
program_type_constants = {"netmc": {"exec_file_name": "netmc.x",
                                    "input_file_name": "netmc.inpt"},
                          "netmc_pores": {"exec_file_name": "netmc_pores.x",
                                          "input_file_name": "netmc.inpt"},
                          "triangle_raft": {"exec_file_name": "mx2.x",
                                            "input_file_name": "mx2.inpt"}}


@dataclass
class Batch:
    name: str
    path: Path
    run_times: list[datetime]
    type: str
    output_files_path: Path

    def __post_init__(self) -> None:
        self.run_times = sorted(self.run_times, reverse=True)
        self.jobs: list[str]
        self.num_jobs: int
        self.last_ran: Optional[datetime]
        try:
            with ZipFile(self.path, "r") as batch_zip:
                self.jobs = [Path(sub_path).parent.name for sub_path in batch_zip.namelist()]
            self.num_jobs = len(self.jobs)
        except FileNotFoundError:
            self.jobs = []
            self.num_jobs = 0
        self.num_runs: int = len(self.run_times)
        try:
            self.last_ran = self.run_times[0]
        except IndexError:
            self.last_ran = None
        self.exec_name: str = program_type_constants[self.type]["exec_file_name"]
        self.input_file_name: str = program_type_constants[self.type]["input_file_name"]
        self.output_path: Path = self.output_files_path.joinpath(self.type, self.name)

    def __str__(self):
        """
        Returns a string representation of the Batch object
        """
        return f"Batch {self.name} ({self.type}) with {self.num_jobs} jobs and ran {self.num_runs} times at: {self.run_times}"

    def __lt__(self, other: Batch) -> bool:
        """
        Compares the last ran times of two Batch objects

        Args:
            other (Batch): The other Batch object to compare to
        Returns:
            bool: True if the last ran time of this Batch is less than the other Batch, False otherwise
            NotImplemented: If the other object is not a Batch object
        """
        if isinstance(other, Batch):
            if self.last_ran is None:
                return True
            elif other.last_ran is None:
                return False
            else:
                return self.last_ran < other.last_ran
        else:
            return NotImplemented

    def submit(self, coulson_username, submit_script_path, output_files_path) -> None:
        """
        Submits the batch to Coulson by launching a background task that runs the submit script
        and checks every 5 seconds if the batch has been completed, and then returns
        the output files as a zip file

        Args:
            coulson_username (str): The username for Coulson
            submit_script_path (Path): The path to the submit script
            output_files_path (Path): The path to the directory to save the output files
        """
        python_path = executable
        # print(python_path, submit_script_path,
        #                     "-n", self.name,
        #                     "-x", str(self.num_runs),
        #                     "-y", self.type,
        #                     "-p", self.path,
        #                     "-o", output_files_path,
        #                     "-u", coulson_username)
        background_process([python_path, submit_script_path,
                            "-n", self.name,
                            "-x", str(self.num_runs),
                            "-y", self.type,
                            "-p", self.path,
                            "-o", output_files_path,
                            "-u", coulson_username])
        self.num_runs += 1
        self.last_ran = datetime.now(timezone.utc)
        self.run_times.append(self.last_ran)

    def convert_to_array(self, t_zone: timezone = timezone.utc) -> Tuple[str, int, int, str]:
        """
        Converts the Batch object to an array for use in a table

        Args:
            t_zone (timezone): The timezone to convert the last ran time to
        Returns:
            The array representation of the Batch object
        """
        if self.last_ran is None:
            last_ran = "-"
        else:
            last_ran = self.last_ran.astimezone(t_zone).strftime("%Y %a %d %b %H:%M:%S")
        return (self.name, self.num_jobs, self.num_runs, last_ran)

    def convert_to_export_array(self) -> list[Tuple[str, str, datetime]]:
        """
        Converts the Batch object to an array for exporting to a CSV file

        Returns:
            The array representation of the Batch object
        """
        return [(self.name, self.type, time) for time in self.run_times]

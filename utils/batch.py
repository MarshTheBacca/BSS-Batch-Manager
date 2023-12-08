import os
from zipfile import ZipFile
from datetime import datetime, timezone

from .other_utils import background_process

program_type_constants={"netmc": {"exec_file_name":"netmc.x",
                                  "input_file_name":"netmc.inpt"},
                        
                        "netmc_pores": {"exec_file_name":"netmc_pores.x",
                                        "input_file_name":"netmc.inpt"},
                        
                        "triangle_raft": {"exec_file_name":"mx2.x",
                                          "input_file_name":"mx2.inpt"}}


class Batch:
    def __init__(self, name, path, run_times, program_type, output_files_path):
        self.name = name
        self.path = path
        self.run_times = sorted(run_times, reverse = True)
        try:
            with ZipFile(path, "r") as batch_zip:
                self.jobs = [os.path.basename(os.path.dirname(sub_path)) for sub_path in batch_zip.namelist()]
            self.num_jobs = len(self.jobs)
        except FileNotFoundError:
            self.jobs = []
            self.num_jobs = None
        self.num_runs = len(run_times)
        try:
           self.last_ran = run_times[0]
        except IndexError:
            self.last_ran = None
        self.type = program_type
        self.prog_name = program_type
        self.exec_name = program_type_constants[program_type]["exec_file_name"]
        self.input_file_name = program_type_constants[program_type]["input_file_name"]
        self.output_path = os.path.join(output_files_path, self.type, self.name)
    def __str__(self):
        return (f"Batch_Obj: {self.name}, {self.type}, {self.num_jobs}, {self.num_runs}, {self.run_times}")
        
    def __lt__(self, other):
        if self.last_ran == None:
            return True
        elif other.last_ran == None:
            return False
        else:
            return self.last_ran < other.last_ran
        
    def submit(self, coulson_username, submit_script_path, output_files_path):
        background_process(["python", submit_script_path, 
                            "-n", self.name, 
                            "-x", str(self.num_runs), 
                            "-y", self.type, 
                            "-p", self.path,
                            "-o", output_files_path, 
                            "-u", coulson_username])
        self.num_runs += 1
        self.last_ran = datetime.now(timezone.utc)
        self.run_times.append(self.last_ran)
        
    def convert_to_array(self, t_zone = timezone.utc):
        if self.last_ran == None:
            last_ran = "-"
        else:
            last_ran = self.last_ran.astimezone(t_zone).strftime("%Y %a %d %b %H:%M:%S")
        if self.num_jobs == None:
            num_jobs = "-"
        else:
            num_jobs = self.num_jobs
        return [self.name, num_jobs, self.num_runs, last_ran]
    
    def convert_to_export_array(self, t_zone):
        return [[self.name, self.type, time] for time in self.run_times]
    

    class Run:
        def __init__(self, number: int, path):
            self.num = number
            self.path = os.path.join(path, f"run_{number}")
            
    
    
    
    
from pathlib import Path
from datetime import datetime
from tzlocal import get_localzone

from utils import get_config_options, initialise
from utils import valid_int
from utils import print_table, import_batches, batch_table, export_batches
from utils import Config

program_type_constants = {1: {"program_name": "netmc",
                              "print_name": "NetMC"},
                          2: {"program_name": "netmc_pores",
                              "print_name": "NetMC Pores"},
                          3: {"program_name": "triangle_raft",
                              "print_name": "Triangle Raft"}}

number_orders = {1: "first", 2: "second", 3: "thrid", 4: "fourth", 5: "fifth", 6: "sixth",
                 7: "seventh", 8: "eigth", 9: "nineth", 10: "tenth"}

# Notes for when u return:
# Way of scanning output files for missing files?
# Way of generating grahpics as .svg files automatically
# Extract time to complete batch?
# Extract % success/failiure of batch?

# Windows issue with multiprocessing, once batch is submitted, the integer menu seems to duplicate
# How can we figure out whether to use 'python' or 'python3' for commands on different platforms?
# There is currenty no validation on username or output_files path in config.csv


def get_local_constants(cwd, program_type):
    global program_name
    global input_path, output_path, batch_submit_script_path

    # Program type constants, 1 = NetMC, 2 = Triangle Raft
    program_name = program_type_constants[program_type]["program_name"]

    # Local constants
    input_path = cwd.joinpath("batches", program_name)
    batch_submit_script_path = cwd.joinpath("utils", "batch_submit.py")


def main():
    cwd = Path(__file__).parent
    coulson_username, output_path = get_config_options(cwd.joinpath("config.csv"), [0, 1], cwd)
    initialise(cwd, output_path)
    local_tz = get_localzone()
    local_tz_string = datetime.now(local_tz).tzname()
    while True:
        option = valid_int("What would you like to do?\n1) Generate Batches\n2) Submit Batches to Coulson\n"
                           "3) Analyse Batches\n4) Exit\n", 1, 4)
        if option == 1:
            while True:
                option = valid_int("What type of program would you like to create batches for?"
                                   "\n1) NetMC\n2) NetMC Pores\n3) Triangle Raft\n4) Exit\n", 1, 4)
                if option == 4:
                    break
                else:
                    get_local_constants(cwd, option)
                    dims = valid_int("How many variables would you like to vary (10 to exit)\n", 1, 10)
                    if dims != 10:
                        while True:
                            config = Config(program_name)
                            config_table, var_indexes = config.table()
                            print_table(config_table, max_col_lengths=[30, 50, 50, 38],
                                        headers=("Value", "Description", "Type", "Allowed Values"))
                            exit_option = len(config_table) + 1
                            print(f'{exit_option}) Exit\n\nThe current values in the template are given above'
                                  f'\nPlease edit the text file: {program_name}_template.csv in the "common_files" directory to change this\n')
                            changing_var_arrays, chosen_var_indexes = [], []
                            breakout, count, num_jobs = 0, 0, 1
                            while count < dims:
                                if dims == 1:
                                    question_string = "Which variable would you like to change\n"
                                else:
                                    question_string = f"Enter the {number_orders[count + 1]} variable you'd like to change\n"
                                var_option = valid_int(question_string, 1, exit_option)
                                if var_option == exit_option:
                                    breakout = 1
                                    break
                                else:
                                    var = config.variables[var_indexes[var_option - 1]]
                                    print(f"You have selected: {var.name}")
                                    not_exited, changing_var_array = var.get_cva()
                                    if not_exited:
                                        changing_var_arrays.append(changing_var_array)
                                        chosen_var_indexes.append(var_indexes[var_option - 1])
                                        num_jobs = num_jobs * len(changing_var_array)
                                        count += 1
                            if breakout == 1:
                                break
                            else:
                                batch_name = input("Please enter a batch name for the folder these input files will be in\n")
                                config.generate_batch(changing_var_arrays, chosen_var_indexes, input_path, batch_name)
                                print(f"Successfully created batch with {num_jobs} jobs")
        elif option == 2:
            while True:
                option = valid_int("Which program type would you like to submit?\n1) NetMC\n2) NetMC Pores\n3) Triangle Raft\n4) Exit\n", 1, 4)
                if option == 4:
                    break
                else:
                    get_local_constants(cwd, option)
                    while True:
                        batches = import_batches("batch_history.txt", output_path)
                        batches_table = batch_table(batches, program_name, local_tz)
                        batch_names = [batch.name for batch in batches]
                        exit_option = len(batches_table) + 1
                        if exit_option == 1:
                            print("There are no batches to submit!\n")
                            break
                        print("\n")
                        print_table(batches_table, headers=("Batch Name", "Number of Jobs", "Number of Times Submitted",
                                                            "Last Time Submitted (" + local_tz_string + ")"), dims=2)
                        print(f"{exit_option}) Exit\n")
                        option = valid_int("Which batch would you like to submit?\n", 1, exit_option)
                        if option != exit_option:
                            selected_batch = batches[batch_names.index(batches_table[option - 1][0])]
                            selected_batch.submit(coulson_username, batch_submit_script_path, output_path)
                            export_batches("batch_history.txt", batches)
                            print(f"\nSuccessfully submitted {selected_batch.name}!")
                        else:
                            break
        elif option == 3:
            print("Not yet implemented")
        elif option == 4:
            break


if __name__ == "__name__":
    main()

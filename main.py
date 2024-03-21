from utils import LAMMPSNetMCInputData, get_valid_int
from pathlib import Path

NUMBER_ORDERS = {1: "first", 2: "second", 3: "third", 4: "fourth", 5: "fifth", 6: "sixth", 7: "seventh", 8: "eighth",
                 9: "ninth", 10: "tenth"}


def main():
    common_files_path = Path(__file__).parent.joinpath("common_files")
    batches_path = Path(__file__).parent.joinpath("batches")
    template_data = LAMMPSNetMCInputData.from_file(common_files_path.joinpath("lammps_netmc_template.inpt"))
    while True:
        option = get_valid_int("What would you like to do?\n1) Create a batch\n"
                               "2) Edit the batch template\n3) Submit batch to Coulson\n4) Exit\n", 1, 4)
        if option == 1:
            num_vars = get_valid_int("How many variables would you like to vary? (10 to exit)\n", 1, 10)
            if num_vars == 10:
                continue
            exit_num = len(template_data.table_relevant_variables) + 1
            selected_var_indexes = []
            vary_arrays = []
            cancelled = False
            while len(selected_var_indexes) < num_vars:
                template_data.table_print(relevant_only=True)
                option = get_valid_int(f"Enter the {NUMBER_ORDERS[len(selected_var_indexes) + 1]} variable ({exit_num} to exit)\n", 1, exit_num)
                if option == exit_num:
                    cancelled = True
                    break
                if option - 1 in selected_var_indexes:
                    print("You have already selected this variable")
                    continue
                selected_var_indexes.append(option - 1)
                print(f"You have selected {template_data.table_relevant_variables[option - 1].name}")
                vary_array = template_data.table_relevant_variables[option - 1].get_vary_array()
                if vary_array is None:
                    cancelled = True
                    break
                vary_arrays.append(vary_array)
            if cancelled:
                continue
            template_data.generate_batch(vary_arrays, selected_var_indexes, batches_path)

        elif option == 2:
            template_data.edit_value_interactive()
            template_data.export(common_files_path.joinpath("lammps_netmc_template.inpt"))

        elif option == 3:
            pass
        elif option == 4:
            break


if __name__ == "__main__":
    main()

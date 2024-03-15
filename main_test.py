from utils import LAMMPSNetMCInputData, get_valid_int
from pathlib import Path


def main():
    common_files_path = Path(__file__).parent.joinpath("common_files")
    template_data = LAMMPSNetMCInputData.from_file(common_files_path.joinpath("lammps_netmc_template.inpt"))
    while True:
        option = get_valid_int("What would you like to do?\n1) Create a batch\n"
                               "2) Edit the batch template\n3) Submit batch to Coulson\n4) Exit\n", 1, 4)
        if option == 4:
            break
        elif option == 1:
            pass
        elif option == 2:
            template_data.edit_value_interactive()


if __name__ == "__main__":
    main()

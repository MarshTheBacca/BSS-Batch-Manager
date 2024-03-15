from utils import LAMMPSNetMCInputData
from pathlib import Path
cwd = Path(__file__).parent
input_data = LAMMPSNetMCInputData.from_file(cwd.joinpath("netmc.inpt"))
input_data.table_print()
input_data.export(cwd.joinpath("netmc_2.inpt"))

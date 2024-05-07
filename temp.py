from pathlib import Path

from utils import BSSData

from matplotlib import pyplot as plt

run_path = Path(__file__).parent.joinpath("output_files", "rings_196_max_36_2_new", "run_1")
first_job = next(run_path.joinpath("jobs").iterdir())
print(f"First job: {first_job}")
bss_data = BSSData.from_files(first_job.joinpath("output_files"), run_path.joinpath("initial_network", "fixed_rings.txt"))
bss_data.draw_graph_pretty()
plt.show()
plt.clf()
bss_data.plot_ring_size_distribution()
plt.show()

import os
from tqdm import tqdm
LAB = 2

lab_dir =os.path.join('data', f'Lab{LAB}')
if not os.path.isdir(lab_dir):
    raise FileNotFoundError(f'Lab{LAB} directory not found in data directory')

for dirname in tqdm(os.listdir(lab_dir)):
    for filename in os.listdir(os.path.join(lab_dir, dirname)):
        if filename.endswith('.ipynb'):
            os.system(f'jupyter nbconvert --to html "{os.path.join(lab_dir, dirname, filename)}"')

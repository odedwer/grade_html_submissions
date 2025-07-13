import os
from tqdm import tqdm
LAB = 5

lab_dir =os.path.join('data', f'lab{LAB}')
if not os.path.isdir(lab_dir):
    raise FileNotFoundError(f'lab{LAB} directory not found in data directory')

for dirname in tqdm(os.listdir(lab_dir)):
    if not os.path.isdir(os.path.join(lab_dir, dirname)):
        if dirname.endswith('.ipynb'):
            os.system(f'jupyter nbconvert --to html "{os.path.join(lab_dir, dirname)}"')
        continue
    for filename in os.listdir(os.path.join(lab_dir, dirname)):
        if filename.endswith('.ipynb'):
            os.system(f'jupyter nbconvert --to html "{os.path.join(lab_dir, dirname, filename)}"')

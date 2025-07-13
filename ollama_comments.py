import json
import os
import re

import nbformat
import ollama
import nbformat
from nbconvert import HTMLExporter

OLLAMA_MODEL = "gemma3n:latest"
LAB = 5  # Specify the lab number
data_directory = os.path.join(os.path.abspath('data'), f'lab{LAB}')  # Absolute path to the data directory


def make_tree(path):
    tree = {}
    for dirname, subdirs, files in os.walk(path):
        # Ensure the directory path is relative for URL use
        relative_dir = os.path.relpath(dirname, data_directory)
        tree[relative_dir] = []
        for file in files:
            if file.endswith('.ipynb'):
                file_path = os.path.join(relative_dir, file)
                text_file_path = file_path.replace('.ipynb', '.html')
                tree[relative_dir].append(text_file_path.replace(os.sep, '/'))  # Use URL friendly slashes

    # order the dict by the second hebrew word in the key
    tree = {k: v for k, v in sorted(tree.items(), key=lambda item: item[0].split('_')[0].split(' ')[1] if len(
        item[0].split('_')) > 1 else item[0]) if k != '.' and k != '..'}

    return tree


def extract_member_ids(directory, ipynb_file):
    ipynb_path = os.path.join(directory, ipynb_file)
    with open(ipynb_path, 'r', encoding='utf-8') as f:
        notebook_data = json.load(f)
    # Extract `group_members_ids` from the first code cell
    group_members_ids = None
    for cell in notebook_data.get('cells', []):
        if cell.get('cell_type') == 'code':
            try:
                group_members_ids = cell.get('source', [])[-1]  # Get the last line of the code cell
                group_members_ids = group_members_ids[group_members_ids.find("=") + 1:group_members_ids.find(
                    "#")].strip()  # Extract the value after '='
                break
            except IndexError:
                continue
    return group_members_ids


def get_groups():
    groups = dict()
    # Loop through all folders in the data directory
    for folder_name in os.listdir(data_directory):
        folder_path = os.path.join(data_directory, folder_name)
        if os.path.isdir(folder_path):
            # find the ipynb file in the folder, search for it
            ipynb_file = next((f for f in os.listdir(folder_path) if f.endswith('.ipynb')), None)
            if ipynb_file:
                # Extract group members' IDs from the notebook

                group_members_ids = extract_member_ids(folder_path, ipynb_file)
                if group_members_ids:
                    if group_members_ids not in groups:
                        groups[group_members_ids] = []
                    groups[group_members_ids].append(folder_name)


files_tree = make_tree(data_directory)

student_notebook_path = files_tree[list(files_tree.keys())[0]][0]  # Get the first notebook file path
full_solution_path = os.path.join(data_directory, "lab{}_full_solution.html".format(LAB))

try:
    with open(os.path.join(data_directory, student_notebook_path), 'r') as f:
        student_notebook_content = f.read()
except FileNotFoundError:
    print(f"Error: Student notebook not found at {os.path.join(data_directory, student_notebook_path)}")
    # exit()

try:
    with open(full_solution_path, 'r') as f:
        full_solution_content = f.read()
except FileNotFoundError:
    print(f"Error: Full solution code not found at {full_solution_path}")
    # exit()


# %%

def get_questions_and_answers(contents):
    """
    Extracts question and answer cells from the notebook contents.
    Questions are identified by 'question' in their source, and answers by 'answer'.
    """
    question_cells = [(i, cell) for i, cell in enumerate(contents['cells']) if
                      re.search(r'question \d+', cell['source'].lower())]
    answer_cells = [(i, cell) for i, cell in enumerate(contents['cells']) if
                    re.search(r'answer \d*', cell['source'].lower())]
    answer_cells.extend(
        [(i + 1, contents['cells'][i + 1]) for i, cell in question_cells if i + 1 < len(contents['cells'])])

    # remove duplicates based on the cell index
    answer_cells = sorted(list({i: (i, cell) for i, cell in answer_cells}.values()), key=lambda x: x[0])

    return question_cells, answer_cells

with open('data/lab5/lab5_full_solution.ipynb', 'r'):
    correct_contents = nbformat.read(f, as_version=4)
_, answer_cells_correct = get_questions_and_answers(correct_contents)


# %% convert the question cells to html, with source and output

def convert_cells_to_html(stud_file):
    with open(stud_file, 'r', encoding='utf-8') as f:
        nb = nbformat.read(f, as_version=4)
    q_cells, a_cells = get_questions_and_answers(nb)
    indices = [i for i, cell in q_cells]
    indices.extend([i for i, cell in a_cells])
    indices = sorted(set(indices))  # Unique and sorted indices
    nb.cells = [nb.cells[i] for i in cell_indices if i < len(nb.cells)]
    for i, cell in cells:
        if cell['cell_type'] == 'code':
            source = "\n".join(cell['source'])
            outputs = ""
            if 'outputs' in cell:
                for output in cell['outputs']:
                    if 'text' in output:
                        outputs += "<pre>{}</pre>".format("\n".join(output['text']))
                    elif 'data' in output:
                        if 'text/plain' in output['data']:
                            outputs += "<pre>{}</pre>".format(output['data']['text/plain'])
                        elif 'image/png' in output['data']:
                            outputs += "<img src='data:image/png;base64,{}'>".format(output['data']['image/png'])

            html_content += f"<div class='code-cell'><h3>Cell {i} (Code)</h3><pre>{source}</pre>{outputs}</div>"
        elif cell['cell_type'] == 'markdown':
            html_content += f"<div class='markdown-cell'><h3>Cell {i} (Markdown)</h3>{cell['source']}</div>"
    return html_content


stud_file = 'data/lab5/אופיר בראל_936191_assignsubmission_file/Copy_of_DS4All_Lab_5_Dimensionality_Reduction.ipynb'
# Convert the answer cells to HTML
question_html = convert_cells_to_html(question_cells)
answer_html = convert_cells_to_html(answer_cells)
correct_answer_html = convert_cells_to_html(answer_cells_correct)
# Combine the question and answer HTML
combined_html = f"""
<div class='questions-answers-correct-answers'>
    <h2>Questions and Answers</h2>
    <div class='questions'>{question_html}</div>
    <div class='answers'>{answer_html}</div>
    <div class='correct-answers'>{answer_html}</div>
</div>
"""

prompt = f"""
You are a helpful teaching assistant reviewing a student's Jupyter notebook submission, converted to an HTML file, starting with questions, then the student answers and then the correct answers.
Here is the HTML file with the student's submission and the correct solution:
{combined_html}

-----
Task:
Analyze the student's code and output. Explain the errors, suggest improvements, and compare the student's approach to the correct solution.
Provide comments on the student's submission, only for places where their solution and approach differs from the correct solution.
In you comments, make sure that you start with the part and question numbers, and that you highlight:
- Key differences or missing steps.
- Potential areas for improvement or clarification.
- Specific feedback on code and textual answers.
- What was right and what was wrong in their textual answers.
- Whether they answered all parts of the question.

Respond with concise and clear comments. Only provide comments for the parts that differ from the correct solution, and that require feedback.
Your response should be structured as follows:
* part 1 Question 1: [Your comments here]
* part 1 Question 2: [Your comments here]
...
* part N Question X: [Your comments here]
"""

response = ollama.generate(model=OLLAMA_MODEL, prompt=prompt,
                           options={'num_ctx': 2 ** 14})

# %%
with open('chk.html', 'w') as f:
    f.write(combined_html)

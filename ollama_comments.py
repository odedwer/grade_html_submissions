import json
import os
import re
from collections import defaultdict
from pyexpat.errors import messages
from time import time as get_time
import nbformat
import ollama
import nbformat
from nbconvert import HTMLExporter
import threading
import time
import ollama
import base64
from io import BytesIO
from PIL import Image
from tqdm import tqdm

OLLAMA_MODEL = "llava:7b"
LAB = 5  # Specify the lab number
data_directory = os.path.join(os.path.abspath('data'), f'lab{LAB}')  # Absolute path to the data directory


def keep_model_alive(model='gemma3:27b-it-qat', interval=300):
    def ping():
        while True:
            try:
                ollama.chat(
                    model=model,
                    messages=[{'role': 'system', 'content': 'keepalive'}],
                    stream=False  # avoids printing tokens
                )
            except Exception as e:
                print(f"[keepalive error] {e}")
            time.sleep(interval)

    thread = threading.Thread(target=ping, daemon=True)
    thread.start()


def make_tree(path):
    tree = {}
    for dirname, subdirs, files in os.walk(path):
        # Ensure the directory path is relative for URL use
        relative_dir = os.path.relpath(dirname, data_directory)
        tree[relative_dir] = []
        for file in files:
            if file.endswith('.ipynb'):
                file_path = os.path.join(relative_dir, file)
                # text_file_path = file_path.replace('.ipynb', '.html')
                tree[relative_dir].append(file_path.replace(os.sep, '/'))  # Use URL friendly slashes

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


def get_questions_and_answers(contents):
    """
    Extracts question and answer cells from the notebook contents.
    Questions are identified by 'question' in their source, and answers by 'answer'.
    """
    question_cells = {re.search(r'part\s*\d+\s*-\s*question \d+', cell['source'].lower())[0]: (i, cell) for i, cell in
                      enumerate(contents['cells']) if
                      re.search(r'question \d+', cell['source'].lower()) and 'your code goes here' not in cell[
                          'source'].lower() and 'textual answer' not in cell[
                          'source'].lower() and "#@title part " not in cell['source'].lower()}

    answer_cells = [(i, cell) for i, cell in enumerate(contents['cells']) if
                    re.search(r'answer \d*', cell['source'].lower()) and i not in [idx for idx, _ in
                                                                                   question_cells.values()]]
    answer_cells.extend(
        [(i + 1, contents['cells'][i + 1]) for i, cell in question_cells.values() if
         i + 1 < len(contents['cells']) and i + 1 not in [idx for idx, _ in answer_cells]])

    # remove duplicates based on the cell index
    answer_cells = sorted(list({i: (i, cell) for i, cell in answer_cells}.values()), key=lambda x: x[0])

    # group the answer cells into arrays, one cell array per question based on the question re match
    answer_cells_dict = {}
    for q in question_cells.keys():
        answer_cells_dict[q] = []
        for i, cell in answer_cells:
            search_res = re.search(r'part\s*\d+\s*-\s*question \d+', cell['source'].lower())
            if not search_res or q != search_res[0]:
                continue

            answer_cells_dict[q].append((i, cell))

    return question_cells, answer_cells


def resize_base64_image(base64_str, max_size=256):
    # Step 1: Decode base64 to image
    image_data = base64.b64decode(base64_str)

    image = Image.open(BytesIO(image_data)).convert("RGB")  # force RGB to avoid mode issues
    image.verify()
    # Step 2: Resize while maintaining aspect ratio
    image.thumbnail((max_size, max_size), Image.LANCZOS)  # LANCZOS = high-quality downscaling

    # Step 3: Re-encode to base64 (as PNG or JPEG)
    output_buffer = BytesIO()
    image.save(output_buffer, format="PNG")  # or "JPEG" to reduce even more
    resized_bytes = output_buffer.getvalue()
    return base64.b64encode(resized_bytes).decode("utf-8")


def cell_to_src_and_outputs(cell):
    """
    Convert a notebook cell to its source code and outputs.
    """
    source = cell['source']
    text_outputs = []
    image_outputs = []
    if 'outputs' in cell:
        for output in cell['outputs']:
            if 'data' not in output:
                continue
            for key in output['data']:
                if 'text/plain' == key:
                    text_outputs.append(output['data'][key])
                elif 'image/png' == key:
                    image_outputs.append(resize_base64_image(output['data'][key].replace('\n', '')))
    if text_outputs:
        source = "Source:\n" + source + "\n===== Text Outputs: =====\n" + "\n".join(text_outputs) + "\n"
    else:
        source = "Source:\n" + source + "\n"
    return source, image_outputs


# %%

files_tree = make_tree(data_directory)

student_notebook_path = files_tree[list(files_tree.keys())[0]][0]  # Get the first notebook file path
full_solution_path = os.path.join(data_directory, "lab{}_full_solution.ipynb".format(LAB))

try:
    with open(os.path.join(data_directory, student_notebook_path), 'r') as f:
        student_notebook_content = nbformat.read(f, as_version=4)
except FileNotFoundError:
    print(f"Error: Student notebook not found at {os.path.join(data_directory, student_notebook_path)}")
    # exit()

try:
    with open(full_solution_path, 'r') as f:
        full_solution_content = nbformat.read(f, as_version=4)
except FileNotFoundError:
    print(f"Error: Full solution code not found at {full_solution_path}")
    # exit()

# %%


prompt = {'role': 'system',
          'content': """
Act as a teacher assistant reviewing a student's Jupyter notebook submission, given to you in blocks of cells.
You will be given the solution content in one message, followed by the student answer. 

Analyze the student's answer in comparison to the correct solution.
Provide brief, concise comments on the student's submission, only for places where their solution and approach differs from the correct solution.
Never summarize the student's answer, only comment on it.
If you do comment, make sure you only provide the following:
- If the missed part of the question - which part.
- Key differences or missing steps, and errors.

**If there is nothing to comment on, do not provide any comment.**
Never provide improvements or suggestions for code, only comment on the student's answer and figures.
Respond with brief, concise and clear comments.
Only provide the specific comments, without any additional text or explanations.
Comment on the student answer only.
Be brief, focus on textual answers where they exist.
Comment on the content only, and not on styling or formatting.
Provide the comments as if you are addressing the student directly, using "You" and "Your" in your comments.
Don't describe what the student did, unless you are pointing out what is wrong.
"""}
stud_offset = 1

paired_cells = []
for i, ans_cell in enumerate(full_solution_content.cells):
    stud_cell = student_notebook_content.cells[i + stud_offset]
    while ans_cell['metadata']['id'] != stud_cell['metadata']['id']:
        stud_offset += 1
        stud_cell = student_notebook_content.cells[i + stud_offset]
    ans_source, ans_image_outputs = cell_to_src_and_outputs(ans_cell)
    stud_source, stud_image_outputs = cell_to_src_and_outputs(stud_cell)
    paired_cells.append((ans_source, ans_image_outputs, stud_source, stud_image_outputs))
responses = []
lookahead = 10
for i in tqdm(range(len(paired_cells) - lookahead)):
    cells = paired_cells[i:i + lookahead]
    ans_source = "\n".join([cell[0] for cell in cells])
    ans_image_outputs = [img for cell in cells for img in cell[1]]
    stud_source = "\n".join([cell[2] for cell in cells])
    stud_image_outputs = [img for cell in cells for img in cell[3]]
    messages = [
        prompt,
        {
            'role': 'user',
            'content': f"Content from the solution:\n{ans_source}",
            'images': ans_image_outputs,
        },
        {
            'role': 'assistant',
            'content': 'Understood, you have given me the solution, now I will get the student answer and comment as if I\'m directly addressing the student.',
        },
        {
            'role': 'user',
            'content': f"Content from the student:\n{stud_source}",
            'images': stud_image_outputs,
        }
    ]

    response = ollama.chat(
        model=OLLAMA_MODEL,
        messages=messages,
        stream=False
    )
    responses.append(response['message']['content'])

# %% question and answer cell ids
q_ids = dict()
ans_ids = defaultdict(list)
for cell in full_solution_content.cells:
    cell_id = cell['metadata']['id']
    if 'question' in cell['source'].lower():
        q = re.search(r'part\s*\d+\s*-\s*question \d+', cell['source'].lower())
        if q:
            ans_match = re.search(r'textual answer', cell['source'].lower()) #or re.search(
                # r'#@title part\s*\d+\s*-\s*question\s*\d+', cell['source'].lower())
            if ans_match:
                ans_ids[q[0]].append(cell_id)
            else:
                q_ids[q[0]] = cell_id

# %% Take each q and ans, get the student answer and the solution answer, format them for a prompt, and send to Ollama
for q in q_ids.keys():
    ans_cell_ids = ans_ids[q]
    q_cell = student_notebook_content.cells[student_notebook_content.cells.index(
        next(cell for cell in student_notebook_content.cells if cell['metadata']['id'] == q_ids[q]))]
    stud_ans_cells = [student_notebook_content.cells[student_notebook_content.cells.index(
        next(cell for cell in student_notebook_content.cells if cell['metadata']['id'] == q_id))] for q_id in
                      ans_cell_ids]
    sol_ans_cells = [full_solution_content.cells[full_solution_content.cells.index(
        next(cell for cell in full_solution_content.cells if cell['metadata']['id'] == q_id))] for q_id in
                     ans_cell_ids]
    q_src, q_image_outputs = cell_to_src_and_outputs(q_cell)

    stud_ans_srcs = []
    stud_ans_image_outputs = []
    for ans_cell in stud_ans_cells:
        ans_src, ans_image_outputs = cell_to_src_and_outputs(ans_cell)
        stud_ans_srcs.append(ans_src)
        stud_ans_image_outputs.extend(ans_image_outputs)

    sol_ans_srcs = []
    sol_ans_image_outputs = []
    for ans_cell in sol_ans_cells:
        ans_src, ans_image_outputs = cell_to_src_and_outputs(ans_cell)
        sol_ans_srcs.append(ans_src)
        sol_ans_image_outputs.extend(ans_image_outputs)

    messages = [
        prompt,
        {
            'role': 'user',
            'content': f"""
            This is the question: {q_src}
            This is the solution answer: {'\n'.join(sol_ans_srcs)}
            """,
            'images': sol_ans_image_outputs,
        },
        {
            'role': 'assistant',
            'content': 'Understood, you have given me the solution, now I will get the student answer and comment as if I\'m directly addressing the student.',
        },
        {
            'role': 'user',
            'content': f"""
        This is the student answer: {'\n'.join(stud_ans_srcs)}
        """,
            # 'images': stud_ans_image_outputs,
        }
    ]

    response = ollama.chat(
        model=OLLAMA_MODEL,
        messages=messages,
        stream=False
    )
    print(f"* {q}: {response['message']['content']}")

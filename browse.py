from flask import Flask, render_template, send_from_directory, request, redirect, flash, url_for
import os
import json

app = Flask(__name__)
app.secret_key = 'COMDEPRI'  # Set a secret key for session management
LAB = 5  # Specify the lab number
data_directory = os.path.join(os.path.abspath('data'),f'lab{LAB}')  # Absolute path to the data directory


@app.route('/')
def home():
    # Generate the directory tree
    tree = make_tree(data_directory)
    return render_template('index.html', tree=tree)


def make_tree(path):
    tree = {}
    for dirname, subdirs, files in os.walk(path):
        # Ensure the directory path is relative for URL use
        relative_dir = os.path.relpath(dirname, data_directory)
        tree[relative_dir] = []
        for file in files:
            if file.endswith('.html'):
                file_path = os.path.join(relative_dir, file)
                tree[relative_dir].append(file_path.replace(os.sep, '/'))  # Use URL friendly slashes

    # order the dict by the second hebrew word in the key
    tree = {k: v for k, v in sorted(tree.items(), key=lambda item: item[0].split('_')[0].split(' ')[1] if len(item[0].split('_')) > 1 else item[0]) if k!='.' and k!='..'}

    return tree


@app.route('/files/<path:filename>')
def files(filename):
    print(f"Attempting to serve: {filename}")  # Debugging: Output the requested file path
    # Securely construct the file path and serve the file
    return send_from_directory(data_directory, filename)


@app.route('/edit', methods=['GET', 'POST'])
def edit():
    tree = make_tree(data_directory)
    feedback_content = ""

    if request.method == 'POST':
        selected_file = request.form['selected_file']
        # get the directory from the selected file
        directory = os.path.dirname(selected_file)
        file_path = os.path.join(data_directory, directory, 'feedback.txt')

        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as f:
                feedback_content = f.read()

        return render_template('editor.html', tree=tree, selected_file=selected_file, feedback_content=feedback_content)

    return render_template('editor.html', tree=tree, selected_file="", feedback_content=feedback_content)



@app.route('/save-text', methods=['POST'])
def save_text():
    filename = request.form['selected_file']
    text_content = request.form['text_content']

    if filename and text_content:
        file_path = os.path.join(data_directory, filename)
        directory = os.path.dirname(file_path)

        # Locate the `.ipynb` file in the directory
        ipynb_file = next((f for f in os.listdir(directory) if f.endswith('.ipynb')), None)

        if ipynb_file:
            group_members_ids = extract_member_ids(directory, ipynb_file)

            if group_members_ids:
                # Loop through all folders in the data directory
                for folder_name in os.listdir(data_directory):
                    folder_path = os.path.join(data_directory, folder_name)
                    # find the ipynb file in the folder, search for it
                    ipynb_file_new = next((f for f in os.listdir(folder_path) if f.endswith('.ipynb')), None)
                    if ipynb_file_new:
                        group_members_ids_new = extract_member_ids(folder_path, ipynb_file_new)
                        if group_members_ids_new == group_members_ids:
                            # Save the feedback in the relevant folder
                            feedback_file_path = os.path.join(folder_path, 'feedback.txt')
                            with open(feedback_file_path, 'w', encoding='utf-8') as f:
                                f.write(text_content)


        flash(f'Feedback saved successfully in relevant folders!')
        return redirect(url_for('edit'))
    return 'Error: File or text content not provided', 400


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


if __name__ == '__main__':
    app.run(debug=False, port=5050)

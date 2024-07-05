from flask import Flask, render_template, send_from_directory, request, redirect, flash, url_for
import os

app = Flask(__name__)
app.secret_key = 'COMDEPRI'  # Set a secret key for session management

data_directory = os.path.abspath('data')  # Absolute path to the data directory


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
        feedback_path = os.path.join(data_directory, os.path.dirname(selected_file), 'feedback.txt')

        if os.path.exists(feedback_path):
            with open(feedback_path, 'r', encoding='utf-8') as f:
                feedback_content = f.read()

        return render_template('editor.html', tree=tree, selected_file=selected_file, feedback_content=feedback_content)

    return render_template('editor.html', tree=tree, selected_file="", feedback_content=feedback_content)


@app.route('/save-text', methods=['POST'])
def save_text():
    filename = request.form['selected_file']
    text_content = request.form['text_content']
    if filename and text_content:
        # Determine the directory of the selected file
        file_path = os.path.join(data_directory, filename)
        directory = os.path.dirname(file_path)

        # Create a new text file in the same directory
        new_file_path = os.path.join(directory, "feedback.txt")
        with open(new_file_path, 'w', encoding='utf-8') as f:
            f.write(text_content)

        flash(f'{directory} feedback saved successfully!')
        return redirect(url_for('edit'))
    return 'Error: File or text content not provided', 400


if __name__ == '__main__':
    app.run(debug=False)

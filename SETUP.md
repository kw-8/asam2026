## Set up environment
Make sure you have the following installed:
- VScode
- Python 3.12+

Note: within VScode you may find these extensions helpful for QoL
- [indent rainbow](https://marketplace.visualstudio.com/items?itemName=oderwat.indent-rainbow) (for easier reading)
- [jupyter](https://marketplace.visualstudio.com/items?itemName=ms-toolsai.jupyter) officially supported by microsoft

## Set up repo
1. Open your VScode to the folder you want the ASAM 2026 folder to be in.
2. Go to the toolbar and open the terminal.
3. Then enter `git clone "https://github.com/kw-8/asam2026"`. This should copy the github repo to your local PC folder.
4. Go to File → Open Folder → select the cloned `ASAM 2026` folder.
5. Open the terminal (Terminal → New Terminal)
   - Mac: `python3 -m venv .venv` then `source .venv/bin/activate`
   - Windows: `python -m venv .venv` then `.venv\Scripts\activate`
   - You should now see `(.venv)` at the start of the terminal line.
6. Install packages: `pip install -r requirements.txt`
7. Open any notebook → **Select Kernel** (top right) → Python Environments → `.venv`.

## One-time setup
1. In VScode, click the **Accounts** icon (bottom left) → **Sign in with GitHub** → approve in the browser.
2. Open the terminal (Terminal → New Terminal) and run these two lines once, with your own name and the email on your GitHub account:
   ```
   git config --global user.name "Your Name"
   git config --global user.email "you@example.com"
   ```
3. (IF NEEDED) Make your own branch: click the branch name (bottom left, says `main`) → **Create new branch** → type your name → Enter → click **Publish Branch**.

## Get the most recent version
1. Click the **Source Control** icon (left sidebar, the branching icon).
2. Click **⋯** → **Branch** → **Merge…** → choose `origin/main`.

## Save and upload your work
1. In each notebook you changed: **Clear All Outputs** (top toolbar) → save.
2. Open **Source Control**. Changed files are listed under **Changes**.
   - Only your files should be there. If you see data files or `.venv`, stop and ask.
3. Hover over each of your files → click **+** to stage it.
4. Type a short message in the box to explain changes → click **Commit**.
5. Click **Sync Changes**. This downloads others' changes, then uploads yours.
   - If VS Code reports a **conflict**, stop and ask.
6. On GitHub, open a **Pull Request** from your branch into `main`.

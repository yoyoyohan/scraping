# Deploy the site to a free public URL

You can host this Flask app for free and get a URL like `https://your-app-name.onrender.com`. Two simple options:

---

## Option 1: Render (recommended)

1. **Put the project on GitHub**
   - Create a new repo on [github.com](https://github.com).
   - In your project folder, run:
     ```bash
     git init
     git add .
     git commit -m "Initial commit"
     git branch -M main
     git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git
     git push -u origin main
     ```
   - Make sure the `data/` folder (with your CSV files) is **included** in the repo so the site has rankings. If `data/` is large, you can use Git LFS or leave it and push normally.

2. **Sign up and deploy on Render**
   - Go to [render.com](https://render.com) and sign up (free).
   - Click **New** → **Web Service**.
   - Connect your GitHub account and select the repo you just pushed.
   - Use these settings:
     - **Name:** e.g. `nj-soccer-rankings`
     - **Runtime:** Python 3
     - **Build Command:** `pip install -r requirements.txt`
     - **Start Command:** `gunicorn --bind 0.0.0.0:$PORT app:app`
   - Click **Create Web Service**. Render will build and deploy. When it finishes, your site will be at `https://YOUR_SERVICE_NAME.onrender.com`.

3. **Notes**
   - Free tier: the app may “spin down” after 15 minutes of no traffic; the first visit after that can take 30–60 seconds (cold start).
   - Your CSV files in `data/` are deployed with the code, so the rankings and AI use the same data you have locally.

---

## Option 2: PythonAnywhere

1. Create a free account at [pythonanywhere.com](https://www.pythonanywhere.com).
2. Open a **Bash** console and clone your repo (or upload the project).
3. Create a virtualenv and install dependencies:
   ```bash
   python -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
4. In the **Web** tab, add a new web app (Flask), point it to your project folder and the `app` object.
5. Set the **WSGI file** to load `app:app` (e.g. `/home/YOUR_USERNAME/YOUR_PROJECT/app.py` with `application = app` if needed).
6. Your site will be at `https://YOUR_USERNAME.pythonanywhere.com`.

---

## If you don’t use Git yet

- **Render:** You can use their “Deploy from public Git repository” with a repo you create from the project folder (and push the code + `data/`).
- **PythonAnywhere:** You can upload the project as a zip and then unzip it in your home directory and follow the Web/WSGI steps above.

After deployment, share the link (e.g. `https://nj-soccer-rankings.onrender.com`) and anyone can open the rankings and “Ask the AI” tab.

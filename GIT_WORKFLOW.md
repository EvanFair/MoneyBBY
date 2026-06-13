# 🚀 OutreachForge AI - Git Workflow Cheat Sheet

Hey Evan! Use this guide to keep our codebase perfectly synced. Always run these commands from the project root folder.

---

## 🔄 The Golden Rule of Git
> **Always pull before you start coding!** This prevents merge conflicts when Drew or the AI assistant uploads changes.

Run this command first thing when you open your terminal:
```bash
git pull origin main
```

---

## 🛠️ Typical Coding Workflow

### 1. Check your status
To see what files you have modified or added:
```bash
git status
```

### 2. Save your progress (Stage your changes)
To prepare your files for saving:
```bash
git add .
```

### 3. Commit your changes
Create a save point with a message describing what you did:
```bash
git commit -m "added web scraper and api routes"
```

### 4. Push to GitHub
Upload your save points to the cloud so Drew and the AI can get your code:
```bash
git push origin main
```

---

## 🔑 Handling Credentials (If Git asks for a password)

GitHub does not accept your regular password in the command line anymore. You have two options:

### Option A: Use GitHub CLI (Highly Recommended)
If you have GitHub CLI installed, run:
```bash
gh auth login
```
Select `GitHub.com` -> `HTTPS` -> Log in with web browser. This will authenticate your machine forever.

### Option B: Use a Personal Access Token (PAT)
1. Go to GitHub -> Settings -> Developer Settings -> Personal Access Tokens (Classic) -> Generate new token.
2. Check the box for `repo` permissions.
3. Copy the token generated.
4. When `git push` asks for your password in the terminal, **paste the token** (it won't show characters while you paste, just press Enter).

---

## 🚨 What if you get a Merge Conflict?
If you and Drew edit the exact same line of the same file, Git will warn you about a conflict. 
1. Open the file in VS Code.
2. You will see green and blue blocks indicating `Current Change` (yours) and `Incoming Change` (Drew's).
3. Click **Accept Both**, **Accept Current**, or **Accept Incoming** in VS Code.
4. Save the file, run `git add .`, `git commit -m "resolved merge conflict"`, and `git push origin main`.

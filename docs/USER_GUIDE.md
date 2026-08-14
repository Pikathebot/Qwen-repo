# Jarvis Assistant — User Guide

Welcome to Jarvis, your private, lightweight local AI assistant for Windows.

---

## 1. Quick Start

### Launching Jarvis
- **From Taskbar**: Click the **Jarvis Assistant** icon on your Windows taskbar.
- **From Desktop**: Double-click **Jarvis Assistant** on your Desktop.
- **From Terminal**:
  ```powershell
  d:/JARVIS/.venv/Scripts/python d:/JARVIS/run_jarvis.py
  ```

---

## 2. Keyboard Navigation & Controls

Jarvis is designed for frictionless keyboard interaction:

| Shortcut | Action |
| :--- | :--- |
| **`Alt + Space`** | Summon or dismiss the floating Spotlight window from anywhere in Windows |
| **`Ctrl + Space`** | Alternative global summon hotkey |
| **`Enter`** | Submit current prompt |
| **`Escape`** | Hide the floating window |
| **`Tab`** | Cycle routing mode (**Auto** $\rightarrow$ **Normal** $\rightarrow$ **Heavy**) |

---

## 3. Voice Interaction & Wake-Word

Jarvis supports hands-free voice interaction:

1. **Say the Wake-Word**: Say **"Jarvis, ..."** or **"Hey Jarvis, ..."** followed by your query.
2. **Click-to-Speak**: Click the **Microphone icon** in the search bar. The icon will pulse red while listening.
3. **Auto-Submit**: When you finish speaking, your transcribed query is automatically submitted.

---

## 4. Safety Permissions & Action Confirmations

When an operation touches the filesystem or executes system commands, Jarvis evaluates safety tiers:
- **Low-Risk Tools** (`read_file`, `list_directory`): Executed immediately.
- **Confirmation-Required Tools** (`write_file`, `execute_command`, `delete_file`): Jarvis presents an **Action Confirmation Card**:
  - Click **`Approve & Execute`** to authorize the action with a unique cryptographic action token.
  - Click **`Cancel`** to reject.

---

## 5. Adding Custom Skills

You can extend Jarvis with custom skills without writing Python code:

1. Create a `.md` file in the `skills/` directory (e.g. `skills/git_helper.md`):
   ```markdown
   ---
   name: git_helper
   description: Specialized git assistance and repository management
   triggers:
     - git status
     - commit changes
     - git branch
   tools:
     - execute_command
   ---

   # Git Assistant Instructions
   - Always run git status before staging changes.
   - Format commit messages cleanly following Conventional Commits.
   ```
2. Reload skills dynamically in the UI or call `POST http://127.0.0.1:8000/skills/reload`.

---

## 6. Configuring Heavy Mode (OpenRouter)

To enable Heavy Mode cloud reasoning:
1. Open [`backend/.env`](file:///d:/JARVIS/backend/.env).
2. Set your OpenRouter API key:
   ```env
   OPENROUTER_API_KEY="sk-or-v1-..."
   OPENROUTER_DEFAULT_MODEL="deepseek/deepseek-chat"
   ```
3. In the UI, press `Tab` or click the mode badge to toggle **Heavy** mode.

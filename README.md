# LogPY - Advanced System Monitoring & Telemetry Engine

LogPY is a lightweight, Python-based Endpoint Detection and Response (EDR) style monitoring tool. It tracks system telemetry in real-time—including active window changes, clipboard modifications, and file system events—and securely transmits this data to a private Telegram bot. It features a remote control interface via Telegram for taking snapshots, checking system status, and initiating emergency shutdowns.

## 🚀 Features

*   **Real-Time Telemetry:** Monitors active window titles and process IDs.
*   **Clipboard Tracking:** Captures and formats text copied to the system clipboard.
*   **File System Observation:** Watches standard user directories (Desktop, Downloads, Documents) for created, deleted, or renamed files.
*   **Remote Command Interface (Telegram):**
    *   `📊 SYSTEM STATUS`: View active threads and host information.
    *   `📸 CAPTURE SCREEN`: Take a silent snapshot of the host's desktop.
    *   `🛑 STOP MONITORING`: Remotely halt the telemetry engine without killing the process.
    *   `🔴 EMERGENCY SHUTDOWN`: Safely terminate processes and shut down the host PC (requires a 4-digit PIN).
*   **Stealth & Safety:** Operates silently in the background with an initial grace period for authorized administrative overrides.

## 🛠️ Prerequisites & Installation

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/zwei007/LogPY.git
    cd LogPY
    ```
2.  **Install required dependencies:**
    Make sure you have Python 3.8+ installed.
    ```bash
    pip install asyncio psutil plyer python-telegram-bot watchdog pyautogui pyperclip
    ```

## ⚙️ Configuration

Before running or compiling the script, you must configure your secure credentials in the source code. Open `core.py` and locate the `--- CONFIGURATION ---` section:

1.  **`TELEGRAM_TOKEN`**: Create a new bot via [@BotFather](https://t.me/BotFather) on Telegram and paste the token here.
2.  **`MY_CHAT_ID`**: Get your personal Telegram Chat ID (you can use bots like [@userinfobot](https://t.me/userinfobot)) and enter it as an integer.
3.  **`SHUTDOWN_PIN`**: Set a custom 4-digit PIN for the remote emergency shutdown feature.

## 📦 Building the Executable

To deploy LogPY as a standalone background service without requiring Python on the target machine, use PyInstaller:

```bash
pip install pyinstaller
pyinstaller --noconsole --onefile --name LogPY_Core core.py
```

## ⚠️ Ethical Disclaimer
LogPY is developed strictly for `educational purposes`, `personal system administration`, and `authorized ethical security testing`.
Do not use this software on any system or network where you do not have explicit, written permission from the owner. The developer assumes no liability and is not responsible for any misuse or damage caused by this program.

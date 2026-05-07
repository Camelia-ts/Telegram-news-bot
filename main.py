import logging
import json
import os
import feedparser
import asyncio
from typing import Optional
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
from telegram.error import Forbidden, TelegramError

# --- Configuration ---
TOKEN = "8725336750:AAGd7pYLH1QMvRyqM5hGxymeKcFyekw6U-A"
ADMIN_ID = 2070907284
USERS_FILE = "users.json"
FEEDS_FILE = "feeds.json"
SENT_POSTS_FILE = "sent_tweets.json"
CHECK_INTERVAL = 300  # 5 minutes

# --- Logging Setup ---
logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Persistence Helpers
# ──────────────────────────────────────────────
def load_json(filename, default=None):
    if default is None:
        default = []
    if os.path.exists(filename):
        try:
            with open(filename, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading {filename}: {e}")
    return default

def save_json(filename, data):
    try:
        with open(filename, "w") as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving {filename}: {e}")

# ──────────────────────────────────────────────
# Core Broadcast Helper  (asyncio.gather based)
# ──────────────────────────────────────────────
async def send_to_one(bot, chat_id: int, message: str) -> Optional[int]:
    """Send a message to one user. Returns chat_id if user blocked the bot."""
    try:
        logger.info(f"Sending update to [{chat_id}]...")
        await bot.send_message(chat_id=chat_id, text=message, parse_mode="HTML")
    except Forbidden:
        logger.warning(f"User {chat_id} blocked the bot — removing.")
        return chat_id
    except TelegramError as e:
        logger.error(f"Telegram error for {chat_id}: {e}")
    return None

async def broadcast(bot, message: str) -> None:
    """Broadcast a message to ALL users in users.json concurrently."""
    users: list[int] = load_json(USERS_FILE, [])
    if not users:
        logger.info("No users registered. Skipping broadcast.")
        return

    logger.info(f"Broadcasting to {len(users)} user(s)...")
    results = await asyncio.gather(
        *[send_to_one(bot, chat_id, message) for chat_id in users],
        return_exceptions=False,
    )

    # Remove users who blocked the bot
    blocked = [uid for uid in results if uid is not None]
    if blocked:
        users = [u for u in users if u not in blocked]
        save_json(USERS_FILE, users)
        logger.info(f"Removed {len(blocked)} blocked user(s). Active users: {len(users)}")

# ──────────────────────────────────────────────
# Command Handlers
# ──────────────────────────────────────────────
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Register user and send catch-up with latest posts."""
    chat_id = update.effective_chat.id
    users: list[int] = load_json(USERS_FILE, [])

    if chat_id not in users:
        users.append(chat_id)
        save_json(USERS_FILE, users)
        logger.info(f"New user registered: {chat_id}. Total users: {len(users)}")
        await update.message.reply_text(
            "✅ Đã đăng ký thành công!\n"
            "Bạn sẽ nhận được thông báo ngay khi có bài viết mới."
        )

        # Catch-up: send the latest entry from each feed right away
        feeds = load_json(FEEDS_FILE, [])
        if feeds:
            await update.message.reply_text("⏳ Đang lấy tin mới nhất cho bạn...")
            for url in feeds:
                try:
                    feed = feedparser.parse(url)
                    if feed.entries:
                        e = feed.entries[0]
                        title = e.get("title", "No Title")
                        link  = e.get("link", "")
                        msg   = f"{title}\n\n<a href='{link}'>[Link to Post]</a>"
                        await update.message.reply_text(msg, parse_mode="HTML")
                except Exception as err:
                    logger.error(f"Catch-up error for {chat_id} / {url}: {err}")
    else:
        await update.message.reply_text("Bạn đã có trong danh sách nhận tin rồi.")


async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Unsubscribe user."""
    chat_id = update.effective_chat.id
    users: list[int] = load_json(USERS_FILE, [])
    if chat_id in users:
        users.remove(chat_id)
        save_json(USERS_FILE, users)
        logger.info(f"User unsubscribed: {chat_id}")
        await update.message.reply_text("❌ Đã hủy đăng ký. Bạn sẽ không nhận tin nhắn từ Bot nữa.")
    else:
        await update.message.reply_text("Bạn chưa đăng ký nhận tin.")


async def add_rss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin only: add a new RSS feed."""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⚠️ Bạn không có quyền sử dụng lệnh này.")
        return
    if not context.args:
        await update.message.reply_text("Cú pháp: /add <rss_url>")
        return
    url = context.args[0]
    feeds = load_json(FEEDS_FILE, [])
    if url not in feeds:
        feeds.append(url)
        save_json(FEEDS_FILE, feeds)
        await update.message.reply_text(f"✅ Đã thêm nguồn RSS: {url}")
        logger.info(f"Admin added feed: {url}")
    else:
        await update.message.reply_text("Nguồn này đã tồn tại trong danh sách.")


async def list_rss(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all active RSS feeds."""
    feeds = load_json(FEEDS_FILE, [])
    if not feeds:
        await update.message.reply_text("Danh sách nguồn RSS đang trống.")
        return
    text = "📋 Danh sách nguồn RSS:\n\n" + "\n".join(f"• {u}" for u in feeds)
    await update.message.reply_text(text)


async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show current subscriber count (admin only)."""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⚠️ Bạn không có quyền sử dụng lệnh này.")
        return
    users = load_json(USERS_FILE, [])
    feeds = load_json(FEEDS_FILE, [])
    await update.message.reply_text(
        f"📊 Trạng thái Bot:\n"
        f"• Subscribers: {len(users)}\n"
        f"• RSS feeds: {len(feeds)}\n"
        f"• Check interval: {CHECK_INTERVAL}s"
    )

# ──────────────────────────────────────────────
# RSS Polling Job
# ──────────────────────────────────────────────
async def check_and_broadcast(context: ContextTypes.DEFAULT_TYPE):
    """Called every CHECK_INTERVAL seconds by JobQueue."""
    logger.info("⏰ Checking RSS feeds for new posts...")
    feeds    = load_json(FEEDS_FILE, [])
    sent_ids = load_json(SENT_POSTS_FILE, [])
    sent_set = set(sent_ids)

    new_posts = []
    for url in feeds:
        try:
            feed = feedparser.parse(url)
            for entry in reversed(feed.entries):          # oldest → newest
                post_id = entry.get("id") or entry.get("link")
                if post_id and post_id not in sent_set:
                    new_posts.append({
                        "id":    post_id,
                        "title": entry.get("title", "No Title"),
                        "link":  entry.get("link", ""),
                    })
                    sent_set.add(post_id)
        except Exception as e:
            logger.error(f"Error parsing {url}: {e}")

    if not new_posts:
        logger.info("No new posts found.")
        return

    # Persist new IDs immediately (keep last 1 000 entries)
    save_json(SENT_POSTS_FILE, list(sent_set)[-1000:])
    logger.info(f"Found {len(new_posts)} new post(s). Broadcasting...")

    for post in new_posts:
        message = f"{post['title']}\n\n<a href='{post['link']}'>[Link to Post]</a>"
        await broadcast(context.bot, message)
        await asyncio.sleep(0.3)   # small gap between posts

    logger.info("✅ Broadcast complete.")

# ──────────────────────────────────────────────
# Entry Point
# ──────────────────────────────────────────────
if __name__ == "__main__":
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start",  start))
    app.add_handler(CommandHandler("stop",   stop_cmd))
    app.add_handler(CommandHandler("add",    add_rss))
    app.add_handler(CommandHandler("list",   list_rss))
    app.add_handler(CommandHandler("status", status_cmd))

    # Start RSS poller (first check 10 seconds after boot)
    app.job_queue.run_repeating(check_and_broadcast, interval=CHECK_INTERVAL, first=10)

    logger.info("🤖 Bot is running — polling for updates...")
    app.run_polling(drop_pending_updates=True, close_loop=False)

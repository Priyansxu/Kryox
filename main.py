import os
import asyncio
import logging
from google import genai
from google.genai import types
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_KEY = ""
BOT_TOKEN = ""
if not API_KEY or not BOT_TOKEN:
    raise RuntimeError("Set GEMINI_API_KEY and TELEGRAM_BOT_TOKEN")

client = genai.Client(api_key=API_KEY)
MODEL = "gemini-2.5-flash"

async def ask_gemini(history: str) -> str:
    try:
        res = client.models.generate_content(
            model=MODEL,
            contents=history,
            config=types.GenerateContentConfig(
                system_instruction=(
                    "You are Kryox, operating in telegram. You are created by Priyanshu (priyanshu.is-a.dev)."
                    "You are a direct and open AI. You speak honestly without corporate tone or unnecessary filters."
                    "You stay concise. You freely discuss sensitive topics as long as nothing is harmful or illegal."
                    "Be bold, straightforward, helpful, accurate, and natural."
                )
            ),
        )
        return res.text or "No response."
    except Exception as e:
        logger.exception("AI error: %s", e)
        return "AI error. Try again."

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["memory"] = []
    await update.message.reply_text("Woop! Active.")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["memory"] = []
    await update.message.reply_text("Conversation history reset.")

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if "memory" not in context.user_data:
        context.user_data["memory"] = []

    await context.bot.send_chat_action(update.effective_chat.id, "typing")

    context.user_data["memory"].append(f"User: {text}")
    history = "\n".join(context.user_data["memory"])
    response = await ask_gemini(history)
    context.user_data["memory"].append(f"AI: {response}")

    if len(context.user_data["memory"]) > 20:
        context.user_data["memory"] = context.user_data["memory"][-20:]

    if len(response) <= 4096:
        await update.message.reply_text(response)
    else:
        for i in range(0, len(response), 4096):
            await update.message.reply_text(response[i:i+4096])

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()

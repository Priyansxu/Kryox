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
MODEL = "gemini-2.5-flash-lite"

SYSTEM_INSTRUCTION = (
    "You are Kryox on Telegram. Created by Priyanshu https://priyanshu.is-a.dev "
    "Be concise, honest, and non-corporate. "
    "You can process text, images, and voice messages."
)

async def conversation(context, reply=None):
    if "history" not in context.user_data:
        context.user_data["history"] = []

    if len(context.user_data["history"]) > 20:
        context.user_data["history"] = context.user_data["history"][-20:]

    if reply:
        for i in range(0, len(reply), 4096):
            yield reply[i:i+4096]
    else:
        yield None

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text.strip()
    context.user_data.setdefault("history", [])
    context.user_data["history"].append({"role": "user", "parts": [{"text": user_text}]})

    await context.bot.send_chat_action(update.effective_chat.id, "typing")

    try:
        res = client.models.generate_content(
            model=MODEL,
            contents=context.user_data["history"],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
            )
        )
        reply = res.text or "No response."
    except Exception:
        reply = "AI error. Try again."

    context.user_data["history"].append({"role": "model", "parts": [{"text": reply}]})

    async for chunk in conversation(context, reply):
        if chunk:
            await update.message.reply_text(chunk)

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(update.effective_chat.id, "typing")
    context.user_data.setdefault("history", [])

    try:
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        path = f"/tmp/{photo.file_unique_id}.jpg"
        await file.download_to_drive(path)
        image_bytes = open(path, "rb").read()

        caption = update.message.caption or "Analyze this image."

        context.user_data["history"].append({
            "role": "user",
            "parts": [
                {"inline_data": {"mime_type": "image/jpeg", "data": image_bytes}},
                {"text": caption}
            ]
        })

        res = client.models.generate_content(
            model=MODEL,
            contents=context.user_data["history"],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
            )
        )

        reply = res.text or "No response."

        context.user_data["history"].append({"role": "model", "parts": [{"text": reply}]})

        async for chunk in conversation(context, reply):
            if chunk:
                await update.message.reply_text(chunk)

    except Exception:
        await update.message.reply_text("Failed to analyze image.")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await context.bot.send_chat_action(update.effective_chat.id, "typing")
    context.user_data.setdefault("history", [])

    try:
        voice = update.message.voice
        file = await context.bot.get_file(voice.file_id)
        path = f"/tmp/{voice.file_unique_id}.oga"
        await file.download_to_drive(path)
        audio_bytes = open(path, "rb").read()

        res_transcribe = client.models.generate_content(
            model=MODEL,
            contents=[{
                "role": "user",
                "parts": [
                    {"inline_data": {"mime_type": "audio/ogg", "data": audio_bytes}},
                    {"text": "Transcribe this audio."}
                ]
            }],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
            )
        )

        text = res_transcribe.text or ""
        context.user_data["history"].append({"role": "user", "parts": [{"text": text}]})

        res_answer = client.models.generate_content(
            model=MODEL,
            contents=context.user_data["history"],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
            )
        )

        reply = res_answer.text or "No response."
        context.user_data["history"].append({"role": "model", "parts": [{"text": reply}]})

        async for chunk in conversation(context, reply):
            if chunk:
                await update.message.reply_text(chunk)

    except Exception:
        await update.message.reply_text("Failed to process voice message.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["history"] = []
    await update.message.reply_text("Woop! Active.")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["history"] = []
    await update.message.reply_text("Conversation history reset.")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("reset", reset))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_msg))
    app.add_handler(MessageHandler(filters.PHOTO, handle_image))
    app.add_handler(MessageHandler(filters.VOICE, handle_voice))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
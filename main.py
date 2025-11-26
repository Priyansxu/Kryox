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
SYSTEM_INSTRUCTION = (
    "You are Kryox, operating in Telegram. Created by Priyanshu https://priyanshu.is-a.dev. "
    "You are direct, open, concise and natural. You answer honestly without corporate tone. "
    "You can process text, images, and voice messages."
)

async def handle_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if "memory" not in context.user_data:
        context.user_data["memory"] = []

    await context.bot.send_chat_action(update.effective_chat.id, "typing")
    context.user_data["memory"].append(f"User: {text}")
    conversation = "\n".join(context.user_data["memory"])

    try:
        res = client.models.generate_content(
            model=MODEL,
            contents=conversation,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
            ),
        )
        response = res.text or "No response."
    except Exception:
        response = "AI error. Try again."

    context.user_data["memory"].append(f"AI: {response}")
    if len(context.user_data["memory"]) > 20:
        context.user_data["memory"] = context.user_data["memory"][-20:]

    for i in range(0, len(response), 4096):
        await update.message.reply_text(response[i:i+4096])

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.send_chat_action(update.effective_chat.id, "typing")
        photo = update.message.photo[-1]
        file = await context.bot.get_file(photo.file_id)
        path = f"/tmp/{photo.file_unique_id}.jpg"
        await file.download_to_drive(path)

        with open(path, "rb") as f:
            image_bytes = f.read()

        caption = update.message.caption or "Analyze this image."
        if "memory" not in context.user_data:
            context.user_data["memory"] = []

        context.user_data["memory"].append(f"User: {caption}")
        conversation = "\n".join(context.user_data["memory"])

        res = client.models.generate_content(
            model=MODEL,
            contents=[
                types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                conversation
            ],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
            ),
        )

        output = res.text or "No response."
        context.user_data["memory"].append(f"AI: {output}")
        if len(context.user_data["memory"]) > 20:
            context.user_data["memory"] = context.user_data["memory"][-20:]

        for i in range(0, len(output), 4096):
            await update.message.reply_text(output[i:i+4096])
    except Exception:
        await update.message.reply_text("Failed to analyze image.")

async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        await context.bot.send_chat_action(update.effective_chat.id, "typing")
        voice = update.message.voice
        file = await context.bot.get_file(voice.file_id)
        path = f"/tmp/{voice.file_unique_id}.oga"
        await file.download_to_drive(path)

        with open(path, "rb") as f:
            audio_bytes = f.read()

        res_transcribe = client.models.generate_content(
            model=MODEL,
            contents=[types.Part.from_bytes(data=audio_bytes, mime_type="audio/ogg"), "Transcribe this audio."],
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
            ),
        )
        text = res_transcribe.text or ""

        if "memory" not in context.user_data:
            context.user_data["memory"] = []
        context.user_data["memory"].append(f"User: {text}")
        conversation = "\n".join(context.user_data["memory"])

        res_answer = client.models.generate_content(
            model=MODEL,
            contents=conversation,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_INSTRUCTION,
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)
            ),
        )
        response = res_answer.text or "No response."
        context.user_data["memory"].append(f"AI: {response}")
        if len(context.user_data["memory"]) > 20:
            context.user_data["memory"] = context.user_data["memory"][-20:]

        for i in range(0, len(response), 4096):
            await update.message.reply_text(response[i:i+4096])
    except Exception:
        await update.message.reply_text("Failed to process voice message.")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["memory"] = []
    await update.message.reply_text("Woop! Active.")

async def reset(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["memory"] = []
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
# =======================
# Install Required Packages
# =======================
!pip install openai
!pip install python-telegram-bot
!pip install nest_asyncio
!pip install requests beautifulsoup4
!pip install filestack-python
!pip install pymupdf python-docx

# =======================
# Import Libraries
# =======================
import os
import re
import requests
from bs4 import BeautifulSoup
from openai import OpenAI
from typing import Final
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import base64
from io import BytesIO
import filestack
import fitz  # PyMuPDF
from docx import Document
import logging
import asyncio
import nest_asyncio
import csv
from datetime import datetime

# Apply nest_asyncio to allow nested event loops in Colab
nest_asyncio.apply()

# =======================
# API KEYS and BOT CONFIG
# =======================
OPENROUTER_API_KEY = # Your OpenRouter API key
TOKEN = # Your Telegram bot token
BOT_USERNAME = # Your bot username without @
filestack_API_KEY = # Your Filestack API key

# =======================
# MODEL MAPPING
# =======================
# Map model names to the actual model IDs used in OpenRouter or other platforms
def Model(name):
    mapping = {
        "ds": "deepseek/deepseek-chat:free",  # Example: DeepSeek chat model
        "gpt4": "openai/gpt-4o-2024-11-20",   # GPT-4o model
    }
    return mapping.get(name)

# =======================
# OPENROUTER API CALL
# =======================
# Sends a list of messages (conversation history) to the chosen model and returns the model's reply
def Prediction_text_multi(name, messages):
    client = OpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=OPENROUTER_API_KEY
    )
    completion = client.chat.completions.create(
        extra_body={},  # Extra request options if needed
        model=Model(name),
        messages=messages
    )
    return completion.choices[0].message.content

# =======================
# TEXT FORMATTING
# =======================
# Convert text output from LLM to a structured format for display
def Text_to_Structure(text):
    text = text.replace("###", "✅")  # Replace headings with emoji
    text = re.sub(r'\*\*(.*?)\*\*', r'[\1]', text)  # Convert **bold** to [bold]
    return text

# =======================
# FETCH WEBPAGE TEXT
# =======================
# Fetch raw text from a given URL (limit to first 3000 chars)
def fetch_webpage_text(url):
    try:
        response = requests.get(url)
        response.raise_for_status()
    except Exception as e:
        logging.error(f"Error fetching url {url}: {e}")
        return ""
    soup = BeautifulSoup(response.text, 'html.parser')
    return soup.get_text().strip()[:3000]

# =======================
# CRAWL WEBSITE AND SUMMARIZE
# =======================
def crawl_website(url):
    # Extract URL from text using regex
    pattern = r'https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)'
    url = re.findall(pattern, url)[0]
    raw_text = fetch_webpage_text(url)
    # Send the text to the model for summarization
    summary = Prediction_text_multi("gpt4", [
        {"role": "system", "content": "your prompt."},
        {"role": "user", "content": f"Please summarize the following webpage:\n{raw_text}"}
    ])
    return Text_to_Structure(summary)

# =======================
# UPLOAD IMAGE TO FILESTACK
# =======================
def upload_image_to_filestack(image_path):
    client = filestack.Client(filestack_API_KEY)
    new_file = client.upload(filepath=image_path)
    return new_file.url

# =======================
# EXTRACT TEXT FROM FILES
# =======================
# PDF extraction
def extract_text_from_pdf(pdf_path: str) -> str:
    text = ""
    doc = fitz.open(pdf_path)
    for page_num in range(doc.page_count):
        text += doc.load_page(page_num).get_text()
    return text

# Word document extraction
def extract_text_from_word(word_path: str) -> str:
    text = ""
    doc = Document(word_path)
    for paragraph in doc.paragraphs:
        text += paragraph.text + "\n"
    return text

# =======================
# SEND LONG MESSAGES IN TELEGRAM
# =======================
# Telegram has a character limit per message; split long messages into chunks
async def send_long_message(update, text: str):
    max_length = 4000
    parts = [text[i:i+max_length] for i in range(0, len(text), max_length)]
    for part in parts:
        await update.message.reply_text(part)
        await asyncio.sleep(0.5)

# =======================
# CSV LOGGING
# =======================
log_file = "chat_logs.csv"
if not os.path.exists(log_file):
    with open(log_file, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(["timestamp", "user_id", "user_name", "chat_id", "chat_title", "is_gpt_query", "user_message", "bot_response"])

def log_message(update, is_gpt_query, user_message, bot_response):
    user = update.message.from_user
    chat = update.message.chat
    log_entry = [
        datetime.utcnow().isoformat(),
        user.id,
        f"{user.first_name} {user.last_name or ''}".strip(),
        chat.id,
        chat.title,
        is_gpt_query,
        user_message,
        bot_response
    ]
    with open(log_file, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(log_entry)
    print("Logged CSV entry:", log_entry)

# =======================
# CONVERSATION HISTORY PER CHAT
# =======================
conversation_histories = {}
def get_conversation_history(chat_id):
    # Initialize system prompt for new chat
    if chat_id not in conversation_histories:
        conversation_histories[chat_id] = [{"role": "system", "content": "Your prompt."}]
    return conversation_histories[chat_id]

# =======================
# HANDLE TEXT MESSAGES
# =======================
async def handle_message(update, context):
    chat_id = update.message.chat.id
    message_type = update.message.chat.type
    text = update.message.text or ""

    # Only respond in group if bot is mentioned
    if message_type in ["group", "supergroup"]:
        if BOT_USERNAME not in text:
            print("User text message (not addressed):", text)
            log_message(update, "no", text, "")
            return

    print("User text message:", text)
    await update.message.reply_text("I am thinking...", parse_mode="markdown")
    history = get_conversation_history(chat_id)

    # Check for URLs in the text
    url_pattern = r'https?://(?:www\.)?[-a-zA-Z0-9@:%._\+~#=]{1,256}\.[a-zA-Z0-9()]{1,6}\b(?:[-a-zA-Z0-9()@:%_\+.~#?&//=]*)'
    urls = re.findall(url_pattern, text)

    if urls:
        remaining_text = re.sub(url_pattern, "", text).strip()
        combined_raw = ""
        for url in urls:
            combined_raw += fetch_webpage_text(url) + "\n"
        if remaining_text:
            new_user_content = remaining_text + "\n" + combined_raw
        else:
            new_user_content = combined_raw
        history.append({"role": "user", "content": new_user_content})
    else:
        user_message = text.replace(BOT_USERNAME, "").replace("@", "").strip()
        history.append({"role": "user", "content": user_message})

    # Get response from model
    assistant_reply = Prediction_text_multi("gpt4", history)
    history.append({"role": "assistant", "content": assistant_reply})
    response = Text_to_Structure(assistant_reply)

    # Send long messages in parts if needed
    if len(response) > 4096:
        await send_long_message(update, response)
    else:
        await update.message.reply_text(response, parse_mode="markdown")
    log_message(update, "yes" if urls == [] else "mixed", text, response)

# =======================
# HANDLE IMAGE MESSAGES
# =======================
async def handle_photo(update, context):
    chat_id = update.message.chat.id
    caption = update.message.caption or ""

    # Only respond if bot is mentioned
    if update.message.chat.type in ["group", "supergroup"]:
        if BOT_USERNAME not in caption:
            log_message(update, "no", caption, "")
            return

    print("User photo caption:", caption)
    history = get_conversation_history(chat_id)

    # Download image locally
    photo_file = await update.message.photo[-1].get_file()
    file_path = f"downloads/{photo_file.file_id}.jpg"
    os.makedirs("downloads", exist_ok=True)
    await photo_file.download_to_drive(file_path)
    await update.message.reply_text("I am thinking...", parse_mode="markdown")

    # Upload image to Filestack and get URL
    image_url = upload_image_to_filestack(f"/content/{file_path}")

    # Send image URL and caption to model
    raw_msg = {
        "role": "user",
        "content": [
            {"type": "text", "text": caption.strip() if caption.strip() else "Please analyze the following image."},
            {"type": "image_url", "image_url": {"url": image_url}}
        ]
    }
    history.append(raw_msg)
    summary = Prediction_text_multi("gpt4", history)
    history.append({"role": "assistant", "content": f"Image analysis result: {summary}"})

    response = Text_to_Structure(summary)
    if len(response) > 4096:
        await send_long_message(update, f"Image Analysis:\n{response}")
    else:
        await update.message.reply_text(f"Image Analysis:\n{response}", parse_mode="markdown")
    log_message(update, "yes", caption, response)

# =======================
# HANDLE DOCUMENT MESSAGES (PDF / DOCX)
# =======================
async def handle_document(update, context):
    chat_id = update.message.chat.id
    caption = update.message.caption or ""

    # Only respond if bot is mentioned
    if update.message.chat.type in ["group", "supergroup"]:
        if BOT_USERNAME not in caption:
            log_message(update, "no", caption, "")
            return

    print("User document caption:", caption)
    history = get_conversation_history(chat_id)

    # Download document
    file = update.message.document
    file_name = file.file_name
    file_path = f"downloads/{file_name}"
    os.makedirs("downloads", exist_ok=True)
    downloaded_file = await file.get_file()
    await downloaded_file.download_to_drive(file_path)
    await update.message.reply_text("I am thinking...", parse_mode="markdown")

    # Extract text based on file type
    if file_name.endswith(".pdf"):
        text_content = extract_text_from_pdf(file_path)
    elif file_name.endswith(".docx"):
        text_content = extract_text_from_word(file_path)
    else:
        await update.message.reply_text("❓ Unsupported file format.")
        return

    # Combine caption and document text for LLM
    if caption.strip():
        combined_text = caption.strip() + "\n" + text_content
    else:
        combined_text = f"Please summarize the following document ({file_name}):\n" + text_content

    history.append({"role": "user", "content": combined_text})
    summary = Prediction_text_multi("gpt4", history)
    history.append({"role": "assistant", "content": f"Document analysis result: {summary}"})

    response = Text_to_Structure(summary)
    if len(response) > 4096:
        await send_long_message(update, f"Document Analysis:\n{response}")
    else:
        await update.message.reply_text(f"Document Analysis:\n{response}", parse_mode="markdown")
    log_message(update, "yes", combined_text, response)

# =======================
# COMMAND HANDLERS
# =======================
async def start_command(update, context):
    chat_id = update.message.chat.id
    # Reset conversation history for the chat
    conversation_histories[chat_id] = [{"role": "system", "content": "Your prompt"}]
    response = "History cleared."
    await update.message.reply_text(response)
    log_message(update, "command", update.message.text, response)


async def guideline_command(update, context):
    response = (
        "How to Use the Bot:\n\n"
        "1. Start the Bot: In the chat, type `@chatbot_name`, followed by your question or request.\n"
        "2. Ask Questions: You can ask any questions, such as information inquiries, advice, or guidance.\n"
        "3. Upload Files: If needed, you can upload images, documents, or links (make sure to include `@chatbot_name`). The Bot will assist based on your uploads.\n"
        "4. Get Help: If you forget how to use it, type `\\guideline` for usage details.\n"
        "5. Additional Assistance: Type `\\help`, and the Bot will provide further support."
    )
    await update.message.reply_text(response)
    log_message(update, "command", update.message.text, response)

# =======================
# ERROR HANDLING
# =======================
async def error(update, context):
    logging.error(f"❌ Update {update} caused error {context.error}")

# =======================
# MAIN FUNCTION
# =======================
async def main():
    logging.basicConfig(level=logging.INFO)
    app = Application.builder().token(TOKEN).build()

    # Register command handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("guideline", guideline_command))

    # Register message handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_error_handler(error)

    logging.info("🤖 Bot is polling...")
    await app.run_polling(poll_interval=1)

if __name__ == "__main__":
    asyncio.run(main())

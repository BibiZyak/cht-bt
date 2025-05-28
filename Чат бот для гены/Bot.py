from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    BotCommand,
    BotCommandScopeDefault,
)
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
)
import os
import sqlite3
import threading
from flask import Flask, render_template_string
from dotenv import load_dotenv

# ────────── Загрузка переменных окружения ──────────
load_dotenv()
TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

# ────────── Настройка базы данных для аналитики ──────────
conn = sqlite3.connect('analytics.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    event TEXT,
    ts DATETIME DEFAULT CURRENT_TIMESTAMP
)
''')
conn.commit()

def log_event(user, event: str):
    """Сохраняет событие в БД: user.id, user.username, событие и время."""
    user_id = user.id
    username = user.username or f"{user.first_name} {user.last_name or ''}".strip()
    cursor.execute(
        "INSERT INTO events(user_id, username, event) VALUES (?, ?, ?)",
        (user_id, username, event)
    )
    conn.commit()

# ────────── Telegram Bot: тексты и клавиатуры ──────────
FIRST_MESSAGE = '''👋 Добро пожаловать в PIRANIA!

С 2015 года мы создаём сайты и лендинги под ключ на Tilda, Битрикс, Wordpress и других платформах.

📦 Чем можем помочь:
— Оценить Ваш проект и сроки  
— Прислать примеры наших работ  
— Подобрать подходящий формат сайта

📢 Также занимаемся продвижением:
— Яндекс Директ  
— SEO  
— Реклама в соцсетях и другие каналы

🎥 Мы — не просто агентство, а медийная компания, активно ведём соцсети, делимся кейсами и полезным контентом. Нас можно найти здесь:

🔗 Сайты:
🌐 https://ra-pirania.ru  
🌐 https://pirania-ra.ru

📱 Контакты:
👤 Telegram (личный): @RA_PIRANIA  
👥 VK: https://vk.com/zhirnovgenri

📺 Наши медиа-площадки:
▶️ YouTube: https://www.youtube.com/channel/UCMC4fr2Fz9uo2mqjjmAb9LA  
📌 Pinterest: https://ru.pinterest.com/ZhirnovGennady/  
🎬 RuTube: https://rutube.ru/channel/30409260/  
📰 Дзен: https://dzen.ru/ra_pirania  
🎥 VK Видео: https://vkvideo.ru/@pirania_ra

💬 Напишите, что Вам нужно — мы на связи!'''

CASES_LIST = [
    "https://marinadevyatova.ru",
    "https://netievskiy.pro/",
    "https://gusinayalapka.ru",
    "https://cleanbox96.ru/",
    "https://grosko-realty.ru/",
    "https://svetron.pro/",
    "https://iqlabmoscow.ru/",
    "https://tkreka.ru/",
    "https://Katehunter.ru",
    "https://homecleaning.site/",
    "https://belka.team/",
    "https://semerukhinarealty.ru/",
    "https://elkamult.ru/",
    "https://mk-logic.ru",
    "https://usa-baby.us/",
    "https://gastromarketreka.ru/",
    "https://evabrick.ru",
    "https://rus-village.ru/",
    "https://vesnastom.ru/",
    "https://vbg-group.ru/",
    "https://yurchenko-vladimir.ru",
    "https://choosyrecruitment.com",
    "https://voskresenie.band",
    "https://comofissnab.ru",
]
CONTACT_LINK = "https://t.me/RA_PIRANIA"

def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("Кейсы", callback_data='cases'),
         InlineKeyboardButton("Связаться", callback_data='contact')]
    ])

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log_event(update.effective_user, 'start')
    await update.message.reply_text(FIRST_MESSAGE, reply_markup=main_menu_keyboard())

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    if query.data == 'cases':
        log_event(user, 'cases')
        text = "Список кейсов:\n" + "\n".join(f"– {url}" for url in CASES_LIST)
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data='back')]])
        await query.edit_message_text(text, reply_markup=kb)
    elif query.data == 'contact':
        log_event(user, 'contact')
        text = f"Связаться со мной: {CONTACT_LINK}"
        kb = InlineKeyboardMarkup([[InlineKeyboardButton("Назад", callback_data='back')]])
        await query.edit_message_text(text, reply_markup=kb)
    elif query.data == 'back':
        log_event(user, 'back')
        await query.edit_message_text(FIRST_MESSAGE, reply_markup=main_menu_keyboard())

# ────────── Команда получения ID по юзернейму ──────────
async def getid(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or not context.args[0].startswith("@"):
        return await update.message.reply_text("Использование: /getid @username")
    username = context.args[0]
    try:
        chat = await context.bot.get_chat(username)
        await update.message.reply_text(
            f"ID пользователя {username}: `{chat.id}`",
            parse_mode="MarkdownV2"
        )
    except Exception as e:
        await update.message.reply_text(f"❗ Не удалось получить ID: {e}")

# ────────── Flask Web Server для статистики ──────────
webapp = Flask(__name__)

HTML_TEMPLATE = '''
<!doctype html>
<html lang="ru">
<head>
  <meta charset="utf-8">
  <title>Статистика бота PIRANIA</title>
  <style>
    table {border-collapse: collapse; width: 100%;}
    th, td {border: 1px solid #ccc; padding: 8px; text-align: left;}
    th {background: #f4f4f4;}
  </style>
</head>
<body>
  <h1>Статистика бота PIRANIA</h1>
  <table>
    <tr><th>Пользователь</th><th>Событие</th><th>Количество</th><th>Последнее время</th></tr>
    {% for username, event, cnt, last in rows %}
    <tr><td>{{ username }}</td><td>{{ event }}</td><td>{{ cnt }}</td><td>{{ last }}</td></tr>
    {% endfor %}
  </table>
</body>
</html>
'''

@webapp.route('/')
def stats_page():
    cursor.execute(
        "SELECT username, event, COUNT(*) AS cnt, MAX(ts) AS last_ts"
        " FROM events GROUP BY username, event"
    )
    rows = cursor.fetchall()

    # ======== НОВЫЙ БЛОК ДЛЯ КОНВЕРТАЦИИ ВРЕМЕНИ В MSK ========
    from datetime import datetime
    from zoneinfo import ZoneInfo

    converted = []
    for username, event, cnt, last_ts in rows:
        # Парсим ISO-строку из БД
        dt = datetime.fromisoformat(last_ts)
        # Помечаем как UTC и переводим в Москву (UTC+3)
        dt_utc = dt.replace(tzinfo=ZoneInfo('UTC'))
        dt_msk = dt_utc.astimezone(ZoneInfo('Europe/Moscow'))
        # Форматируем обратно в строку
        formatted = dt_msk.strftime('%Y-%m-%d %H:%M:%S')
        converted.append((username, event, cnt, formatted))
    # ======================================================

    return render_template_string(HTML_TEMPLATE, rows=converted)

def run_web():
    webapp.run(host='0.0.0.0', port=5000)

# ────────── Регистрация команд и запуск ──────────
async def on_startup(application):
    # только глобальные команды /start и /getid
    await application.bot.set_my_commands(
        [
            BotCommand("start", "Запустить бота"),
            BotCommand("getid", "Получить ID по @username"),
        ],
        scope=BotCommandScopeDefault(),
    )


def main():
    # Запускаем веб-сервер в фоне
    threading.Thread(target=run_web, daemon=True).start()

    # Запускаем Telegram-бот
    app = ApplicationBuilder().token(TOKEN).post_init(on_startup).build()
    app.add_handler(CommandHandler('start', start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(CommandHandler('getid', getid))

    print("Bot is running...")
    app.run_polling()

if __name__ == '__main__':
    main()

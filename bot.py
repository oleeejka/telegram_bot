import logging
import sqlite3
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, Defaults, MessageHandler, filters, ConversationHandler, CallbackQueryHandler
from telegram.error import BadRequest

# Настройка логирования
logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

# Создание базы данных
def create_database():
    conn = sqlite3.connect('contests.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS contests (
                  id INTEGER PRIMARY KEY,
                  name TEXT,
                  button_text TEXT,
                  show_count INTEGER DEFAULT 0,
                  active INTEGER DEFAULT 1,
                  type TEXT,
                  channel_id TEXT,
                  participant_count INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

# Обновление базы данных
def update_database():
    conn = sqlite3.connect('contests.db')
    c = conn.cursor()
    try:
        c.execute("ALTER TABLE contests ADD COLUMN type TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE contests ADD COLUMN channel_id TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE contests ADD COLUMN show_count INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE contests ADD COLUMN participant_count INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()

# Определение команды /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [
        [InlineKeyboardButton("Начать конкурс", callback_data='start_contest')],
        [InlineKeyboardButton("Частые вопросы", callback_data='faq')],
        [InlineKeyboardButton("Контакты", callback_data='contacts')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text('Привет! Я бот для проведения конкурсов.', reply_markup=reply_markup)

# Обработчик нажатий на кнопки
async def button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    logging.info(f"Callback query data: {query.data}")

    if query.data == 'start_contest':
        keyboard = [
            [InlineKeyboardButton("Конкурс по кнопкам", callback_data='button_contest')],
            [InlineKeyboardButton("Конкурс по комментариям", callback_data='comment_contest')],
            [InlineKeyboardButton("Конкурс реакций в комментариях", callback_data='reaction_contest')],
            [InlineKeyboardButton("Конкурс среди подписчиков", callback_data='subscriber_contest')],
            [InlineKeyboardButton("Конкурс на Голоса", callback_data='voice_contest')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text="Выберите тип конкурса:", reply_markup=reply_markup)
    elif query.data in ['button_contest', 'comment_contest', 'reaction_contest', 'subscriber_contest', 'voice_contest']:
        await query.edit_message_text(text="Пожалуйста, добавьте бота в канал или группу и назначьте его администратором. Затем отправьте сюда ID канала или группы или ссылку на канал в формате @username.")
        context.user_data['contest_type'] = query.data
        return CHANNEL_ID  # Здесь вы возвращаете состояние CHANNEL_ID
    elif query.data == 'show_count_yes':
        context.user_data['show_count'] = 1
        await query.edit_message_text(text="Пожалуйста, укажите название конкурса.")
        return NAME
    elif query.data == 'show_count_no':
        context.user_data['show_count'] = 0
        await query.edit_message_text(text="Пожалуйста, укажите название конкурса.")
        return NAME

# Шаги для создания конкурса
CHANNEL_ID, NAME, SHOW_COUNT, BUTTON_TEXT, POST_LINK, INTERVAL, START_MESSAGE = range(7)

# Обработчик для получения ID канала или группы
async def receive_channel_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    logging.info("Обработчик receive_channel_id вызван")
    channel_id = update.message.text.strip()
    logging.info(f"Received channel ID: {channel_id}")

    if not channel_id:
        await update.message.reply_text("Пожалуйста, отправьте корректный ID канала или группы.")
        return CHANNEL_ID

    # Добавляем @ к имени канала, если оно отсутствует
    if not channel_id.startswith('@'):
        channel_id = f'@{channel_id}'

    try:
        # Проверка, является ли бот администратором канала или группы
        admins = await context.bot.get_chat_administrators(chat_id=channel_id)
        if not any(admin.user.id == context.bot.id for admin in admins):
            await update.message.reply_text("Бот не является администратором этого канала или группы. Пожалуйста, добавьте бота в канал или группу и назначьте его администратором.")
            return CHANNEL_ID

        context.user_data['channel_id'] = channel_id[1:]  # Удаляем символ '@'

        keyboard = [
            [InlineKeyboardButton("Да", callback_data='show_count_yes')],
            [InlineKeyboardButton("Нет", callback_data='show_count_no')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text('Отображать количество участников на кнопке?', reply_markup=reply_markup)
        return SHOW_COUNT
    except BadRequest as e:
        logging.error(f"BadRequest error: {e}")
        await update.message.reply_text("Неверный ID канала или группы. Пожалуйста, отправьте корректный ID.")
        return CHANNEL_ID

# Обработчик для получения названия конкурса
async def receive_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['name'] = update.message.text
    await update.message.reply_text('Пожалуйста, укажите текст кнопки.')
    return BUTTON_TEXT

# Обработчик для получения текста кнопки и отправки сообщения с кнопкой
async def receive_button_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['button_text'] = update.message.text
    conn = sqlite3.connect('contests.db')
    c = conn.cursor()

    # Вставка данных о конкурсе в базу данных
    c.execute("INSERT INTO contests (name, button_text, type, channel_id, show_count) VALUES (?, ?, ?, ?, ?)",
              (context.user_data['name'], context.user_data['button_text'], context.user_data['contest_type'], context.user_data['channel_id'], context.user_data['show_count']))

    conn.commit()
    contest_id = c.lastrowid
    conn.close()

    # Генерация кода для вставки в сообщение или пост
    code = f"@{context.bot.username}?start={contest_id}"

    message = f'Конкурс "{context.user_data["name"]}" создан.\nКнопка будет автоматически добавлена.'

    await update.message.reply_text(message)

    # Отправка сообщения с кнопкой в указанный канал
    keyboard = [[InlineKeyboardButton(context.user_data["button_text"], callback_data=f'contest_{contest_id}')]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    try:
        await context.bot.send_message(chat_id=f"@{context.user_data['channel_id']}", text=f"Конкурс: {context.user_data['name']}", reply_markup=reply_markup)
        logging.info(f"Кнопка отправлена в канал @{context.user_data['channel_id']}")
    except Exception as e:
        logging.error(f"Ошибка при отправке сообщения в канал: {e}")

    return ConversationHandler.END

# Команда для просмотра активных конкурсов
async def list_contests(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    conn = sqlite3.connect('contests.db')
    c = conn.cursor()
    c.execute("SELECT id, name FROM contests WHERE active=1")
    contests = c.fetchall()
    conn.close()

    if contests:
        message = "Активные конкурсы:\n"
        for contest in contests:
            message += f"{contest[0]}: {contest[1]}\n"
        await update.message.reply_text(message)
    else:
        await update.message.reply_text('Нет активных конкурсов.')

# Команда редактирования условий конкурса
async def edit_contest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.args:
        contest_id = context.args[0]
        new_name = context.args[1] if len(context.args) > 1 else None
        new_button_text = context.args[2] if len(context.args) > 2 else None
        conn = sqlite3.connect('contests.db')
        c = conn.cursor()
        if new_name:
            c.execute("UPDATE contests SET name = ? WHERE id = ?", (new_name, contest_id))
        if new_button_text:
            c.execute("UPDATE contests SET button_text = ? WHERE id = ?", (new_button_text, contest_id))
        conn.commit()
        conn.close()
        await update.message.reply_text(f'Конкурс с ID {contest_id} отредактирован.')
    else:
        await update.message.reply_text('Пожалуйста, укажите ID конкурса и новые условия.')

# Команда архивирования конкурса
async def archive_contest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.args:
        contest_id = context.args[0]
        conn = sqlite3.connect('contests.db')
        c = conn.cursor()
        c.execute("UPDATE contests SET active = 0 WHERE id = ?", (contest_id,))
        conn.commit()
        conn.close()
        await update.message.reply_text(f'Конкурс с ID {contest_id} архивирован.')
    else:
        await update.message.reply_text('Пожалуйста, укажите ID конкурса.')

# Команда выгрузки статистики
async def export_statistics(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.args:
        contest_id = context.args[0]
        conn = sqlite3.connect('contests.db')
        c = conn.cursor()
        c.execute("SELECT * FROM contests WHERE id = ?", (contest_id,))
        contest = c.fetchone()
        conn.close()
        if contest:
            message = f"Статистика конкурса ID {contest_id}:\n"
            message += f"Название: {contest[1]}\n"
            message += f"Текст кнопки: {contest[2]}\n"
            message += f"Активен: {'Да' if contest[3] else 'Нет'}\n"
            await update.message.reply_text(message)
        else:
            await update.message.reply_text('Конкурс с указанным ID не найден.')
    else:
        await update.message.reply_text('Пожалуйста, укажите ID конкурса.')

# Функция проверки подписки
def check_subscription(user_id, channel_username):
    # Здесь должна быть логика проверки подписки пользователя на канал
    # Возвращаем True, если пользователь подписан, иначе False
    return True

# Команда проверки подписки
async def check_user_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if context.args:
        user_id = update.message.from_user.id
        channel_username = context.args[0]
        if check_subscription(user_id, channel_username):
            await update.message.reply_text('Вы подписаны на указанный канал.')
        else:
            await update.message.reply_text('Вы не подписаны на указанный канал.')
    else:
        await update.message.reply_text('Пожалуйста, укажите username канала.')

# Обработчик отмены
async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text('Операция отменена.')
    return ConversationHandler.END

# Обработчик нажатий на кнопку для участия в конкурсе
async def handle_contest_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()

    contest_id = query.data.split('_')[1]
    conn = sqlite3.connect('contests.db')
    c = conn.cursor()
    c.execute("SELECT button_text, channel_id, show_count, participant_count FROM contests WHERE id = ?", (contest_id,))
    contest = c.fetchone()
    conn.close()

    if contest:
        button_text = contest[0]
        channel_id = contest[1]
        show_count = contest[2]
        participant_count = contest[3]
        user_id = query.from_user.id

        # Проверка подписки пользователя на канал
        if check_subscription(user_id, channel_id):
            # Увеличиваем количество участников
            conn = sqlite3.connect('contests.db')
            c = conn.cursor()
            c.execute("UPDATE contests SET participant_count = participant_count + 1 WHERE id = ?", (contest_id,))
            conn.commit()
            conn.close()

            await query.edit_message_text(text=f"Вы успешно приняли участие в конкурсе: {button_text}")

            # Обновляем текст кнопки, если нужно отображать количество участников
            if show_count:
                conn = sqlite3.connect('contests.db')
                c = conn.cursor()
                c.execute("SELECT button_text, participant_count FROM contests WHERE id = ?", (contest_id,))
                updated_contest = c.fetchone()
                conn.close()

                if updated_contest:
                    button_text = updated_contest[0]
                    participant_count = updated_contest[1]
                    new_button_text = f"{button_text} ({participant_count})"

                    keyboard = [[InlineKeyboardButton(new_button_text, callback_data=f'contest_{contest_id}')]]
                    reply_markup = InlineKeyboardMarkup(keyboard)

                    try:
                        await context.bot.edit_message_reply_markup(chat_id=query.message.chat.id, message_id=query.message.message_id, reply_markup=reply_markup)
                    except BadRequest as e:
                        logging.error(f"BadRequest error: {e}")
        else:
            await query.edit_message_text(text="Вы должны подписаться на канал, чтобы принять участие в конкурсе.")

# Обработчик сообщений и добавление кнопки для участия в конкурсе
async def handle_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message and update.message.text:
        message_text = update.message.text
        if message_text.startswith(f"@{context.bot.username}?start="):
            contest_id = message_text.split('=')[1]
            conn = sqlite3.connect('contests.db')
            c = conn.cursor()
            c.execute("SELECT button_text FROM contests WHERE id = ?", (contest_id,))
            contest = c.fetchone()
            conn.close()

            if contest:
                button_text = contest[0]
                keyboard = [[InlineKeyboardButton(button_text, callback_data=f'contest_{contest_id}')]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(text=f"Конкурс: {button_text}", reply_markup=reply_markup)

# Обработчик сообщений в группе или канале
async def handle_group_messages(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message and update.message.text:
        message_text = update.message.text
        logging.info(f"Received message in group/channel: {message_text}")
        if message_text.startswith(f"@{context.bot.username}?start="):
            contest_id = message_text.split('=')[1]
            conn = sqlite3.connect('contests.db')
            c = conn.cursor()
            c.execute("SELECT button_text, show_count, participant_count FROM contests WHERE id = ?", (contest_id,))
            contest = c.fetchone()
            conn.close()

            if contest:
                button_text = contest[0]
                show_count = contest[1]
                participant_count = contest[2]

                if show_count:
                    button_text = f"{button_text} ({participant_count})"

                keyboard = [[InlineKeyboardButton(button_text, callback_data=f'contest_{contest_id}')]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                logging.info(f"Sending message with button to chat_id: {update.message.chat.id}")
                await context.bot.send_message(chat_id=update.message.chat.id, text=f"Конкурс: {button_text}", reply_markup=reply_markup)

# Создание конкурса по кнопкам
async def create_button_contest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['contest_type'] = 'button_contest'
    await update.message.reply_text("Пожалуйста, отправьте ID канала или группы.")
    return CHANNEL_ID

# Создание конкурса по комментариям
async def create_comment_contest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['contest_type'] = 'comment_contest'
    await update.message.reply_text("Пожалуйста, отправьте ссылку на пост в канале.")
    return POST_LINK

async def receive_post_link(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['post_link'] = update.message.text
    await update.message.reply_text("Пожалуйста, укажите название конкурса.")
    return NAME

# Создание конкурса реакций в комментариях
async def create_reaction_contest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['contest_type'] = 'reaction_contest'
    await update.message.reply_text("Пожалуйста, отправьте ссылку на пост в канале.")
    return POST_LINK

# Создание конкурса среди подписчиков
async def create_subscriber_contest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['contest_type'] = 'subscriber_contest'
    await update.message.reply_text("Пожалуйста, отправьте ID канала или группы.")
    return CHANNEL_ID

# Создание конкурса на голоса
async def create_voice_contest(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['contest_type'] = 'voice_contest'
    await update.message.reply_text("Пожалуйста, отправьте ID канала или группы.")
    return CHANNEL_ID

# Создание модератора комментариев
async def create_comment_moderator(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Пожалуйста, отправьте ссылку на пост в канале.")
    return POST_LINK

async def receive_moderator_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['post_link'] = update.message.text
    await update.message.reply_text("Пожалуйста, укажите интервал времени для комментариев (в минутах).")
    return INTERVAL

async def receive_interval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['interval'] = int(update.message.text)
    await update.message.reply_text("Модератор комментариев создан.")
    return ConversationHandler.END

# Создание автоприема заявок на подписку
async def create_auto_accept(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("Пожалуйста, отправьте ID канала или группы.")
    return CHANNEL_ID

async def receive_auto_accept_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['channel_id'] = update.message.text
    await update.message.reply_text("Пожалуйста, укажите стартовое сообщение (опционально).")
    return START_MESSAGE

async def receive_start_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['start_message'] = update.message.text
    await update.message.reply_text("Автоприем заявок на подписку создан.")
    return ConversationHandler.END

# Основная функция запуска бота
def main() -> None:
    create_database()  # Создаем базу данных при запуске
    update_database()  # Обновляем базу данных, добавляя столбец type
    app = ApplicationBuilder().token("7909752690:AAGZi5yLbdVGXfDrPEDnqMyLM1MijB8miwc").build()

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(button)],
        states={
            CHANNEL_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_channel_id)],
            SHOW_COUNT: [CallbackQueryHandler(button)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_name)],
            BUTTON_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_button_text)],
            POST_LINK: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_post_link)],
            INTERVAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_interval)],
            START_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_start_message)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)  # Убедитесь, что conv_handler добавлен после entry_points
    app.add_handler(CommandHandler("list_contests", list_contests))
    app.add_handler(CommandHandler("edit_contest", edit_contest))
    app.add_handler(CommandHandler("archive_contest", archive_contest))
    app.add_handler(CommandHandler("export_statistics", export_statistics))
    app.add_handler(CommandHandler("check_subscription", check_user_subscription))
    app.add_handler(CallbackQueryHandler(handle_contest_button, pattern=r'^contest_'))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_messages))
    app.add_handler(MessageHandler(filters.ChatType.GROUP | filters.ChatType.SUPERGROUP | filters.ChatType.CHANNEL, handle_group_messages))

    app.run_polling()

if __name__ == '__main__':
    main()

import os
import logging
import re

from uuid import uuid4

from telegram import InlineKeyboardMarkup, InlineKeyboardButton, InputTextMessageContent, InlineQueryResultArticle, ParseMode
from telegram.ext import (
    Updater, CommandHandler,
    CallbackQueryHandler, RegexHandler,
    MessageHandler, InlineQueryHandler
)
from telegram.ext.filters import Filters

from postgres import conn
from service import goodreads_service
from api import goodreads_api, AuthError, ApiError
from config import TELEGRAM_BOT_TOKEN, PORT, APP_URL
from utils import strip_tags

logging.basicConfig(level=logging.DEBUG,
                    format="%(filename)s[LINE:%(lineno)d]# - "
                           "%(asctime)s - "
                           "%(funcName)s: "
                           "%(message)s")
logger = logging.getLogger(__name__)


def start_handler(update, context):
    text = (
        "Бот разрабатывается для замены приложения *Goodreads.com*. \n"
        " В данный момент имеется возможность управления списками книг, поиска и добавления книг, а также inline поиск. \n "
        "Перед началом работы используйте: \n /authorize, \n "
        "после перехода по ссылке и авторизации нажмите 'Готово!' \n "
        "Для поиска отправьте в сообщении текст. \n"
        "Для просмотра полок используйте /shelves \n"
        "Исходный код: https://github.com/fr33mang/telegram-bookshelf-bot"
    )

    update.message.reply_markdown(text=str(text),
                                  parse_mode=ParseMode.MARKDOWN,
                                  disable_web_page_preview=True)


def search_books(update, context):
    page = 1
    if not update.message:
        logger.info(f"message: {update.callback_query.data}")
        page = int(update.callback_query.data.split(' ')[1])
        search_query = " ".join(update.callback_query.data.split(' ')[2:])
        user_id = update.callback_query.from_user.id
    else:
        logger.info(f"message: {update.message.text}")
        user_id = update.message.from_user.id
        search_query = update.message.text

    logger.info((f"user_id: {user_id}, "
                 f"search_query:{search_query}, "
                 f" page:{page}"))

    try:
        books = goodreads_api.get_search_books(user_id, search_query,
                                               page=page)
    except AuthError as ex:
        logger.error(f"AuthError: user_id {user_id}")
        return context.bot.send_message(user_id, text=str(ex))

    result = []
    for index, book in enumerate(books):
        book_md = (
            f"*{strip_tags(book['title'])}* \n"
            f"{', '.join(book['authors'])}\n"
            f"/book\_{book['id']} "  # noqa
        )
        result.append(book_md)

    buttons = []
    if page > 1:
        callback_data = f'search_books {page-1} {search_query}'
        buttons.append(
            InlineKeyboardButton("⬅️", callback_data=callback_data)
        )

    if books:
        callback_data = f'search_books {page+1} {search_query}'
        buttons.append(
            InlineKeyboardButton("➡️", callback_data=callback_data)
        )

    markup = InlineKeyboardMarkup([buttons])
    if result:
        result = "\n\n".join(result)
    elif page == 1:
        result = "*Ничего не найдено!*"
    else:
        result = "*Это всё!*"

    if update.callback_query:
        update.callback_query.edit_message_text(str(result),
                                                parse_mode=ParseMode.MARKDOWN,
                                                disable_web_page_preview=True,
                                                reply_markup=markup)
    else:
        update.message.reply_markdown(text=str(result),
                                      parse_mode=ParseMode.MARKDOWN,
                                      disable_web_page_preview=True,
                                      reply_markup=markup)


def shelves(update, context):
    if not update.message:
        logger.info(f"message: {update.callback_query.data}")
        user_id = update.callback_query.from_user.id
    else:
        logger.info(f"message: {update.message.text}")
        user_id = update.message.from_user.id

    logger.info(f"user_id: {user_id}")

    try:
        shelves = goodreads_api.get_shelves(user_id)
    except AuthError as ex:
        logger.error(f"AuthError: user_id {user_id}")
        return context.bot.send_message(user_id, text=str(ex))

    buttons = []
    for s in shelves:
        buttons.append(
            [InlineKeyboardButton(f"{s['show_name']}({s['book_count']})",
                                  callback_data=f"books_{s['name']}_1")]
        )

    markup = InlineKeyboardMarkup(buttons)
    if update.callback_query:
        update.callback_query.edit_message_text(text="Выберите полку",
                                                parse_mode=ParseMode.MARKDOWN,
                                                disable_web_page_preview=True,
                                                reply_markup=markup)
    else:
        update.message.reply_markdown("Выберите полку",
                                      parse_mode=ParseMode.MARKDOWN,
                                      disable_web_page_preview=True,
                                      reply_markup=markup)


def books(update, context):
    page = 1
    per_page = 5
    shelf = 'etc'
    if not update.message:
        logger.info(f"message: {update.callback_query.data}")
        shelf = update.callback_query.data.split('_')[1]
        page = int(update.callback_query.data.split('_')[2])
        user_id = update.callback_query.from_user.id
    else:
        logger.info(f"message: {update.message.text}")
        user_id = update.message.from_user.id

    logger.info((f"user_id: {user_id}, "
                 f"shelf:{shelf}, "
                 f" page:{page}"))

    try:
        books = goodreads_api.get_books(user_id, page, per_page, shelf)
    except AuthError as ex:
        logger.error(f"AuthError: user_id {user_id}")
        return context.bot.send_message(user_id, text=str(ex))

    result = []
    for book in books:
        book['link'] = f"[→]({book['link']})"
        book_md = (
            f"*{strip_tags(book['title'])}* "
            f"{book['link']}\n"
            f"{', '.join(book['authors'])}\n"
            f"/book\_{book['id']} "  # noqa
        )

        result.append(book_md)

    result = "\n\n".join(result) if result else "*Это всё!*"

    logger.info(str(result))

    buttons = [[]]
    if page > 1:
        buttons[0].append(
            InlineKeyboardButton("⬅️", callback_data=f'books_{shelf}_{page-1}')
        )

    if len(books) == per_page:
        buttons[0].append(
            InlineKeyboardButton("➡️", callback_data=f'books_{shelf}_{page+1}')
        )

    buttons.append(
        [InlineKeyboardButton("Список полок ↩️", callback_data='shelves')]
    )

    markup = InlineKeyboardMarkup(buttons)
    if update.callback_query:
        update.callback_query.edit_message_text(str(result),
                                                parse_mode=ParseMode.MARKDOWN,
                                                disable_web_page_preview=True,
                                                reply_markup=markup)
    else:
        update.message.reply_markdown(text=str(result),
                                      parse_mode=ParseMode.MARKDOWN,
                                      disable_web_page_preview=True,
                                      reply_markup=markup)


def _book_buttons(shelf, book_id, user_id):
    shelves = goodreads_api.get_shelves(user_id)

    shelves = {shelf['show_name']: shelf['name'] for shelf in shelves}
    shelves['Remove 🗑'] = "remove" if shelf else None

    buttons = []
    for text, value in shelves.items():
        if text != 'Remove 🗑':
            button_text = text if shelf != value else f"{text} 📚"
            callback_data = f'add_to_shelf {value} {book_id}'
        elif bool(shelf):
            button_text = 'Remove 🗑'
            callback_data = f'rm_from_shelf {shelf} {book_id}'
        else:
            continue

        button = [InlineKeyboardButton(button_text, callback_data=callback_data)]
        buttons.append(button)

    markup = InlineKeyboardMarkup(buttons)

    return markup


def book(update, context):
    user_id = update.message.from_user.id
    book_id = update.message.text.split('_')[1]

    logger.info((f"user_id: {user_id}, "
                 f"book_id:{book_id}"))

    try:
        book = goodreads_api.get_book(user_id, book_id)
    except AuthError as ex:
        logger.error(f"AuthError: user_id {user_id}")
        return context.bot.send_message(user_id, text=str(ex))

    markup = _book_buttons(book.get('shelf'), book_id, user_id)

    update.message.reply_text(text=strip_tags(book['markdown']),
                              parse_mode=ParseMode.MARKDOWN,
                              reply_markup=markup)


def add_to_shelf(update, context):
    query = update.callback_query
    logger.info(f"query: {query}")

    shelf, book_id = query.data.split(' ')[1:3]
    user_id = query.from_user.id

    remove = "rm_from_shelf" in query.data

    logger.info((f"user_id: {user_id}, "
                 f"shelf:{shelf}, "
                 f" book_id:{book_id}, "
                 f" remove:{remove}"))

    try:
        response_text = goodreads_api.add_to_shelf(user_id, shelf,
                                                   book_id, remove=remove)
    except (AuthError, ApiError) as ex:
        logger.error(str(ex))
        return context.bot.send_message(user_id, str(ex))

    context.bot.answer_callback_query(query.id, response_text)

    if remove:
        shelf = None
    markup = _book_buttons(shelf, book_id, user_id)

    update.callback_query.edit_message_reply_markup(reply_markup=markup)


def inlinebook(update, context):
    user_id = update.callback_query.from_user.id
    book_id = update.callback_query.data.split(' ')[1]

    logger.info((f"user_id: {user_id}, "
                 f"book_id:{book_id}, "
                 f"query: {update.callback_query.data}"))

    try:
        book = goodreads_api.get_book(user_id, book_id)
    except AuthError as ex:
        logger.error(f"AuthError: user_id {user_id}")
        return context.bot.send_message(user_id, text=str(ex))

    markup = _book_buttons(book.get('shelf'), book_id, user_id)

    context.bot.send_message(user_id,
                             text=strip_tags(book['markdown']),
                             parse_mode=ParseMode.MARKDOWN,
                             reply_markup=markup)


def inlinequery(update, context):
    query = update.inline_query.query
    user_id = update.inline_query.from_user.id
    page = int(update.inline_query.offset or 1)

    logger.info(f"query: {query}, page: {page}")

    try:
        books = goodreads_api.get_search_books(user_id, query, page=page, per_page=20)
    except AuthError as ex:
        logger.error(f"AuthError: user_id {user_id}")
        result = [(
            InlineQueryResultArticle(
                id=uuid4(),
                title="Запустите бота!",
                description="Для использования бота, нажмите на кнопку выше, и авторизуйтесь в Goodreads, согласно инструкции",
                input_message_content=InputTextMessageContent("None"),
            )
        )]

        return update.inline_query.answer(result, cache_time=0, switch_pm_text="Добавить бота", switch_pm_parameter="f")

    result = []
    for index, book in enumerate(books):
        book_md = (
            f"*{strip_tags(book['title'])}* \n"
            f"{', '.join(book['authors'])}\n"
            f"[На сайте 🌎](https://www.goodreads.com/book/show/{book['id']})"
        )

        result.append(
            InlineQueryResultArticle(
                id=uuid4(),
                title=strip_tags(book["title"]),
                thumb_url=book["image_url"],
                description=f"{', '.join(book['authors'])}",
                input_message_content=InputTextMessageContent(
                    book_md,
                    ParseMode.MARKDOWN
                ),
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("Добавить книгу 📚", callback_data=f"inlinebook {book['id']}")]])
            )
        )

    update.inline_query.answer(result, next_offset=page + 1)


# TODO: prevent multiple /autorize
def authorize(update, context):
    req_token, req_token_secret = goodreads_service.get_request_token(
                                                        header_auth=True
                                                    )
    authorize_url = goodreads_service.get_authorize_url(req_token)

    user_id = update.message.from_user.id
    with conn.cursor() as cur:
        cur.execute("INSERT INTO tokens (id, request_token, "
                    "                     request_token_secret) "
                    "VALUES(%s, %s, %s)"
                    "ON CONFLICT DO NOTHING", (user_id, req_token,
                                               req_token_secret))
    conn.commit()

    logger.info(f"Authorize, sending url to user: {str(user_id)}")

    markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton('Готово!', callback_data='check_auth')]]
    )
    text = f'Для авторизации бота перейдите по ссылке: {authorize_url}'

    update.message.reply_text(text=text,
                              reply_markup=markup)


def check_auth(update, context):
    query = update.callback_query
    user_id = query.from_user.id

    with conn.cursor() as cur:
        cur.execute("SELECT request_token, request_token_secret "
                    "FROM tokens where id = %s", (user_id,))
        tokens = cur.fetchone()

    try:
        session = goodreads_service.get_auth_session(*tokens)
    except KeyError:
        logger.error(f"authorize error: user_id {user_id}")
        context.bot.answer_callback_query(query.id, "Ошибка авторизации!")
        return

    goodreads_id = goodreads_api.me(session)

    logger.info(f"Success auth, user_id: {user_id}")
    with conn.cursor() as cur:
        cur.execute("UPDATE tokens "
                    "SET (access_token, access_token_secret, "
                    "     goodreads_id) = (%s, %s, %s) "
                    "WHERE id = %s", (session.access_token,
                                      session.access_token_secret,
                                      goodreads_id,
                                      user_id))
    conn.commit()

    update.callback_query.edit_message_text(str(f"Авторизован:{goodreads_id}")) 


updater = Updater(TELEGRAM_BOT_TOKEN,  use_context=True)

updater.dispatcher.add_handler(CommandHandler('start', start_handler))

updater.dispatcher.add_handler(CommandHandler('authorize', authorize))
updater.dispatcher.add_handler(
    CallbackQueryHandler(check_auth, pattern='check_auth')
)

updater.dispatcher.add_handler(CommandHandler('shelves', shelves))
updater.dispatcher.add_handler(
    CallbackQueryHandler(shelves, pattern='shelves')
)

updater.dispatcher.add_handler(CommandHandler('books', books))
updater.dispatcher.add_handler(
    CallbackQueryHandler(books, pattern='books_')
)

updater.dispatcher.add_handler(
    MessageHandler(Filters.regex(r'^/book_\d*$'), book)
)

updater.dispatcher.add_handler(
    CallbackQueryHandler(add_to_shelf, pattern='add_to_shelf')
)

updater.dispatcher.add_handler(
    CallbackQueryHandler(add_to_shelf, pattern='rm_from_shelf')
)

updater.dispatcher.add_handler(
    CallbackQueryHandler(inlinebook, pattern='inlinebook')
)

updater.dispatcher.add_handler(InlineQueryHandler(inlinequery))

updater.dispatcher.add_handler(CommandHandler('search_books', search_books))
updater.dispatcher.add_handler(
    CallbackQueryHandler(search_books, pattern='search_books')
)
updater.dispatcher.add_handler(
    MessageHandler(Filters.text, callback=search_books)
)

if os.environ.get("HEROKU"):
    updater.start_webhook(listen="0.0.0.0",
                          port=PORT,
                          url_path=TELEGRAM_BOT_TOKEN)
    updater.bot.set_webhook(f"{APP_URL}/{TELEGRAM_BOT_TOKEN}")
else:
    updater.start_polling()

updater.idle()

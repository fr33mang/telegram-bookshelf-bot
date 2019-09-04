import os
import logging
import re
from xml.etree import ElementTree

from telegram.ext import (
    Updater, CommandHandler,
    CallbackQueryHandler, RegexHandler,
    MessageHandler
)
from telegram.ext.filters import Filters
from telegram import InlineKeyboardMarkup, InlineKeyboardButton, ParseMode

from postgres import conn
from service import goodreads_service #, db
from api import goodreads_api, AuthError, ApiError
from config import TELEGRAM_BOT_TOKEN, PORT, APP_URL  #, TELEGRAM_PROXY_CONF

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s - %(name)s - %(message)s')
logger = logging.getLogger()


def start_handler(bot, update):
    text = (
        "Этот бот разрабатывается для замены приложения *Goodreads.com*. \n"
        "В данный момент имеется возможность управление списками книг, "
        "а также, для поиска и добавления новых книг. \n"
        "Перед началом работы используйте: \n /authorize, \n"
        "после перехода по ссылке и авторизации нажмите 'Готово!' \n"
        "Для просмотра полок используйте /shelves \n"
    )

    update.message.reply_markdown(text=str(text),
                                  parse_mode=ParseMode.MARKDOWN,
                                  disable_web_page_preview=True)


def search_books(bot, update):
    page = 1
    if not update.message:
        logger.info(f"search_books message: {update.callback_query.data}")
        page = int(update.callback_query.data.split(' ')[1])
        search_query = " ".join(update.callback_query.data.split(' ')[2:])
        user_id = update.callback_query.from_user.id
    else:
        logger.info(f"search_books message: {update.message.text}")
        user_id = update.message.from_user.id
        search_query = update.message.text

    logger.info(f"search_books: {search_query}")

    try:
        # books = get_search_books(user_id, search_query, page=page)
        books = goodreads_api.get_search_books(user_id, search_query, page=page)
    except AuthError as ex:
        return bot.send_message(user_id, text=str(ex))

    result = []
    for index, book in enumerate(books):
        book_md = (
            f"*{book['title']}* \n"
            f"{', '.join(book['authors'])}\n"
            f"/book\_{book['id']} "  # noqa
        )
        result.append(book_md)

    buttons = []
    if page > 1:
        buttons.append(
            InlineKeyboardButton("<", callback_data=f'search_books {page-1} {search_query}')
        )

    if books:
        buttons.append(
            InlineKeyboardButton(">", callback_data=f'search_books {page+1} {search_query}')
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


def shelves(bot, update):
    page = 1
    if not update.message:
        page = int(update.callback_query.data.split('_')[1])
        user_id = update.callback_query.from_user.id
    else:
        user_id = update.message.from_user.id

    try:
        shelves = goodreads_api.get_shelves(user_id, page)
    except AuthError as ex:
        return bot.send_message(user_id, text=str(ex))

    buttons = []
    for s in shelves:
        buttons.append(
            [InlineKeyboardButton(s["name"],
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


def books(bot, update):
    # logger.debug(f"Message from user {update.message.from_user.id}")
    page = 1
    per_page = 5
    shelf = 'etc'
    if not update.message:
        shelf = update.callback_query.data.split('_')[1]
        page = int(update.callback_query.data.split('_')[2])
        user_id = update.callback_query.from_user.id
    else:
        user_id = update.message.from_user.id

    try:
        books = goodreads_api.get_books(user_id, page, per_page, shelf)
    except AuthError as ex:
        return bot.send_message(user_id, text=str(ex))

    result = []
    for book in books:
        book['link'] = f"[->]({book['link']})"
        book_md = (
            f"*{book['title']}* "
            f"{book['link']}\n"
            f"{', '.join(book['authors'])}\n"
            f"/book\_{book['id']} "  # noqa
        )

        result.append(book_md)

    result = "\n\n".join(result) if result else "*Это всё!*"

    logger.info(str(result))

    buttons = []
    if page > 1:
        buttons.append(
            InlineKeyboardButton("<", callback_data=f'books_{shelf}_{page-1}')
        )

    if len(books) == per_page:
        buttons.append(
            InlineKeyboardButton(">", callback_data=f'books_{shelf}_{page+1}')
        )

    markup = InlineKeyboardMarkup([buttons])
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


def _book_buttons(shelf, book_id):
    shelves = {
        'to read': 'to-read',
        'reading': 'currently-reading',
        'read': 'read',
        '🗑': "remove" if shelf else None,
    }

    buttons = []
    for text, value in shelves.items():
        if text != '🗑':
            button_text = text if shelf != value else f"👉{text}"
            callback_data = f'add_to_shelf {value} {book_id}'
        elif bool(shelf):
            button_text = '🗑'
            callback_data = f'rm_from_shelf {shelf} {book_id}'
        else:
            continue

        button = InlineKeyboardButton(button_text, callback_data=callback_data)
        buttons.append(button)

    markup = InlineKeyboardMarkup([
        buttons
    ])

    return markup


def book(bot, update):
    user_id = update.message.from_user.id
    book_id = update.message.text.split('_')[1]

    try:
        book = goodreads_api.get_book(user_id, book_id)
    except AuthError as ex:
        return bot.send_message(user_id, text=str(ex))

    markup = _book_buttons(book.get('shelf'), book_id)

    update.message.reply_photo(photo=book['image'],
                               caption=book['markdown'],
                               parse_mode=ParseMode.MARKDOWN,
                               reply_markup=markup)


def add_to_shelf(bot, update):
    query = update.callback_query
    shelf, book_id = query.data.split(' ')[1:3]
    user_id = query.from_user.id

    remove = "rm_from_shelf" in query.data

    try:
        response_text = goodreads_api.add_to_shelf(user_id, shelf, book_id, remove=remove)
    except (AuthError, ApiError) as ex:
        return bot.send_message(user_id, str(ex))

    bot.answer_callback_query(query.id, response_text)

    if remove:
        shelf = None
    markup = _book_buttons(shelf, book_id)

    update.callback_query.edit_message_reply_markup(reply_markup=markup)


# TODO: prevent multiple /autorize
def authorize(bot, update):
    req_token, req_token_secret = goodreads_service.get_request_token(header_auth=True)
    authorize_url = goodreads_service.get_authorize_url(req_token)

    user_id = update.message.from_user.id
    # db.hmset(user_id, {'req_token': req_token,
    #                    'req_token_secret': req_token_secret})
    with conn.cursor() as cur:
        cur.execute("INSERT INTO tokens (id, request_token, request_token_secret) "
                    "VALUES(%s, %s, %s)"
                    "ON CONFLICT DO NOTHING", (user_id, req_token, req_token_secret))
    conn.commit()

    # logger.info(f"authorize: {str(db.hgetall(user_id))}")

    markup = InlineKeyboardMarkup(
        [[InlineKeyboardButton('Готово!', callback_data='check_auth')]]
    )
    text = f'Для авторизации бота перейдите по ссылке: {authorize_url}'

    update.message.reply_text(text=text,
                              reply_markup=markup)


def check_auth(bot, update):
    query = update.callback_query
    user_id = query.from_user.id

    # tokens = db.hmget(user_id, ['req_token', 'req_token_secret'])
    with conn.cursor() as cur:
        cur.execute("SELECT request_token, request_token_secret FROM tokens where id = %s", (user_id,))
        tokens = cur.fetchone()

    try:
        session = goodreads_service.get_auth_session(*tokens)
    except KeyError:
        bot.answer_callback_query(query.id, "Ошибка авторизации!")
        return

    response_content = goodreads_api.check_auth(session)

    root = ElementTree.fromstring(response_content)
    goodreads_id = root.find('user').attrib['id']

    logger.info(f"access_token => {session.access_token}")
    user_dict = {
        'access_token': session.access_token,
        'access_token_secret': session.access_token_secret,
        'goodreads_id': goodreads_id,
    }
    # db.hmset(user_id, user_dict)
    with conn.cursor() as cur:
        cur.execute("UPDATE tokens "
                    "SET (access_token, access_token_secret, goodreads_id) = (%s, %s, %s) "
                    "WHERE id = %s", (session.access_token, session.access_token_secret, goodreads_id, user_id))
    conn.commit()

    # logger.info(f"Success auth: {str(db.hgetall(user_id))}")
    update.callback_query.edit_message_text(str(f"Авторизован! id {goodreads_id}"))
    # bot.answer_callback_query(query.id, f"Авторизован! id {goodreads_id}")


# updater = Updater(TELEGRAM_BOT_TOKEN, request_kwargs=TELEGRAM_PROXY_CONF)
updater = Updater(TELEGRAM_BOT_TOKEN)

updater.dispatcher.add_handler(CommandHandler('start', start_handler))

updater.dispatcher.add_handler(CommandHandler('authorize', authorize))
updater.dispatcher.add_handler(
    CallbackQueryHandler(check_auth, pattern='check_auth')
)

updater.dispatcher.add_handler(CommandHandler('search_books', search_books))
updater.dispatcher.add_handler(
    CallbackQueryHandler(search_books, pattern='search_books')
)
updater.dispatcher.add_handler(
    MessageHandler(Filters.text, callback=search_books)
)

updater.dispatcher.add_handler(CommandHandler('shelves', shelves))

updater.dispatcher.add_handler(CommandHandler('books', books))
updater.dispatcher.add_handler(
    CallbackQueryHandler(books, pattern='books_')
)

updater.dispatcher.add_handler(
    RegexHandler(re.compile(r'^/book_\d*$'), book)
)

updater.dispatcher.add_handler(
    CallbackQueryHandler(add_to_shelf, pattern='add_to_shelf')
)

updater.dispatcher.add_handler(
    CallbackQueryHandler(add_to_shelf, pattern='rm_from_shelf')
)

if os.environ.get("HEROKU"):
    updater.start_webhook(listen="0.0.0.0",
                          port=PORT,
                          url_path=TELEGRAM_BOT_TOKEN)
    updater.bot.set_webhook(f"{APP_URL}/{TELEGRAM_BOT_TOKEN}")
else:
    updater.start_polling()

updater.idle()

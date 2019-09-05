from xml.etree import ElementTree
from service import _session

from config import CONSUMER_KEY


class AuthError(Exception):
    pass


class ApiError(Exception):
    pass


def session_decorator(func):
    def wrapper(*args, **kwargs):
        session = _session(args[0])
        if not session:
            raise AuthError("Пожалуйста, используйте /authorize")

        kwargs['session'] = session
        return func(*args[1:], **kwargs)

    return wrapper


class GoodreadsAPI():
    @staticmethod
    def check_auth(session=None):
        response = session.get('/api/auth_user')

        return response.content

    @staticmethod
    @session_decorator
    def get_search_books(search_query, page=1, per_page=5, session=None):
        params = {
            "q": search_query,
            "key": CONSUMER_KEY,
            "page": page,
            "per_page": 5,
        }
        response = session.get(f'/search/index.xml',
                               params=params)

        root = ElementTree.fromstring(response.content)

        books = []
        book_fields = ['title', 'id']
        for entry in root.iter('best_book'):
            book = {field: entry.find(field).text for field in book_fields}
            authors = [auth.find('name').text for auth in entry.iter('author')]
            book['authors'] = authors

            books.append(book)

        return books

    @staticmethod
    @session_decorator
    def get_shelves(page=1, per_page=5, session=None):
        params = {
            "key": CONSUMER_KEY,
            "format": "xml",
            "page": page,
            "per_page": per_page,
        }
        response = session.get(f'/shelf/list.xml',
                               params=params)

        root = ElementTree.fromstring(response.content)

        shelf_fields = frozenset(['book_count', 'name'])
        shelves = []

        for shelf in root.iter('user_shelf'):
            shelf = {field: shelf.find(field).text for field in shelf_fields}

            shelves.append(shelf)

        return shelves

    @staticmethod
    @session_decorator
    def get_books(page=1, per_page=5, shelf="etc", session=None):
        params = {
            "v": 2,
            "key": CONSUMER_KEY,
            "format": "xml",
            "page": page,
            "shelf": shelf,
            "per_page": per_page,
        }
        response = session.get(f'/review/list',
                               params=params)

        root = ElementTree.fromstring(response.content)

        book_fields = frozenset(['id', 'title', 'publication_year', 'link'])
        books = []
        for entry in root.iter('book'):
            book = {field: entry.find(field).text for field in book_fields}

            authors = [auth.find('name').text for auth in entry.iter('author')]
            book['authors'] = authors

            books.append(book)

        return books

    @staticmethod
    @session_decorator
    def get_book(book_id, session=None):
        params = {
            "key": CONSUMER_KEY,
            "format": "xml",
        }
        response = session.get(f'/book/show/{book_id}.xml',
                               params=params)
        root = ElementTree.fromstring(response.content)

        book_xml = root.find('book')

        book_fields = ['id', 'title', 'description', 'image_url', 'small_image_url', 'link']
        book = {field: book_xml.find(field).text for field in book_fields}

        authors = book_xml.find("authors")
        book['authors'] = [a.find('name').text for a in authors.iter('author')]

        shelf_xml = root.find("./book/my_review/shelves/shelf")

        book_md = (
            f"*{book['title']}* [на сайте]({book['link']})\n"
            f"{', '.join(book['authors'])}\n\n"
        )
        description = book.get('description')
        if description:
            book_md = book_md + f"{book['description'][:100]}\n"

        return {
            "markdown": book_md,
            "image": book['image_url'],  # or book['small_image_url']
            "shelf": shelf_xml.attrib['name'] if shelf_xml is not None else None,
        }

    @staticmethod
    @session_decorator
    def add_to_shelf(shelf, book_id, remove=False, session=None):
        # can also remove book from shelf (tnx for greads developers)

        params = {
            'name': shelf,
            'book_id': book_id,
            # 'a': 'remove',
        }
        if remove:
            params['a'] = 'remove'

        response = session.get(f'shelf/add_to_shelf.xml',
                               params=params)

        if response.status_code not in (200, 201):
            raise ApiError("Ошибка добавления!")

        message = "Книга добавлена на полку!"
        if remove:
            message = "Книга удалена!"

        return message


goodreads_api = GoodreadsAPI()

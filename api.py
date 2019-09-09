from xml.etree import ElementTree
from service import _session

from config import CONSUMER_KEY


class AuthError(Exception):
    pass


class ApiError(Exception):
    pass


def session_decorator(func):
    def wrapper(self, *args, **kwargs):
        session = _session(args[0])
        if not session:
            raise AuthError("Пожалуйста, используйте /authorize")

        kwargs['session'] = session
        return func(self, *args[1:], **kwargs)

    return wrapper


class GoodreadsAPI():
    def me(self, session=None):
        response = session.get('/api/auth_user')

        root = ElementTree.fromstring(response.content)
        goodreads_id = root.find('user').attrib['id']

        return goodreads_id

    @session_decorator
    def get_search_books(self, search_query, page=1, per_page=5, session=None):
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

    @session_decorator
    def get_shelves(self, page=1, per_page=5, session=None):
        goodreads_id = self.me(session=session)

        params = {
            "key": CONSUMER_KEY,
            "user_id": goodreads_id,
            "format": "xml",
        }
        response = session.get(f'/shelf/list.xml',
                               params=params)

        root = ElementTree.fromstring(response.content)

        shelf_fields = frozenset(['book_count', 'name'])
        shelves = []

        for shelf in root.iter('user_shelf'):
            shelf = {field: shelf.find(field).text for field in shelf_fields}
            shelf['show_name'] = " ".join(shelf['name'].split("-")).title()

            shelves.append(shelf)

        return shelves[::-1]

    @session_decorator
    def get_books(self, page=1, per_page=5, shelf="etc", session=None):
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

    @session_decorator
    def get_book(self, book_id, session=None):
        params = {
            "key": CONSUMER_KEY,
            "format": "xml",
        }
        response = session.get(f'/book/show/{book_id}.xml',
                               params=params)
        root = ElementTree.fromstring(response.content)

        book_xml = root.find('book')

        book_fields = [
            'id', 'title', 'description',
            'image_url', 'small_image_url', 'link'
        ]
        book = {field: book_xml.find(field).text for field in book_fields}

        authors = book_xml.find("authors")
        book['authors'] = [a.find('name').text for a in authors.iter('author')]

        shelf_xml = root.find("./book/my_review/shelves/shelf")

        book_md = (
            f"*{book['title']}* \n"
            f"{', '.join(book['authors'])}\n\n"
        )
        description = book.get('description')
        if description:
            book_md = book_md + f"{book['description'][:200]}... "

        book_md = book_md + f"[на сайте]({book['link']})\n"

        response = {
            "markdown": book_md,
            "image": book['image_url'] or book['small_image_url']
        }
        if shelf_xml is not None:
            response['shelf'] = shelf_xml.attrib['name']

        return response

    @session_decorator
    def add_to_shelf(self, shelf, book_id, remove=False, session=None):
        # can also remove book from shelf (tnx for greads developers)

        params = {
            'name': shelf,
            'book_id': book_id,
        }
        if remove:
            params['name'] = 'to-read'
            response = session.get(f'shelf/add_to_shelf.xml',
                                   params=params)
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

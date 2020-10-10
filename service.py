from rauth.service import OAuth1Service

from config import CONSUMER_KEY, CONSUMER_SECRET
from postgres import conn


class MyOAuth1Service(OAuth1Service):
    def get_db_tokens_session(self, user_id):
        with conn.cursor() as cur:
            cur.execute("SELECT access_token, access_token_secret "
                        "FROM tokens "
                        "where id = %s", (user_id,))
            tokens = cur.fetchone()

        if tokens and all(tokens):
            return super().get_session(token=tokens)


goodreads_service = MyOAuth1Service(
    consumer_key=CONSUMER_KEY,
    consumer_secret=CONSUMER_SECRET,
    name='goodreads',
    request_token_url='https://www.goodreads.com/oauth/request_token',
    authorize_url='https://www.goodreads.com/oauth/authorize',
    access_token_url='https://www.goodreads.com/oauth/access_token',
    base_url='https://www.goodreads.com/'
)

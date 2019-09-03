from rauth.service import OAuth1Service
from vedis import Vedis

from config import CONSUMER_KEY, CONSUMER_SECRET

db = Vedis('vedis.db')

goodreads_service = OAuth1Service(
    consumer_key=CONSUMER_KEY,
    consumer_secret=CONSUMER_SECRET,
    name='goodreads',
    request_token_url='https://www.goodreads.com/oauth/request_token',
    authorize_url='https://www.goodreads.com/oauth/authorize',
    access_token_url='https://www.goodreads.com/oauth/access_token',
    base_url='https://www.goodreads.com/'
)


def _session(user_id):
    user = db.hgetall(user_id)
    print(user)

    try:
        tokens = (user[b'access_token'], user[b'access_token_secret'])
        session = goodreads_service.get_session(tokens)
    except KeyError:
        return None

    return session

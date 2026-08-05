1. Swap the redis with upstash instance of redis
2. swap the rq with QStash
given below are the samples for the usage:
```python 
from qstash.client import QStash

client = QStash("QSTASH_URL", "QSTASH_TOKEN")

client.publish(
    url="https://example.com",
)
```
for redis:
```python
import redis
import os

r = redis.Redis.from_url(os.environ["REDIS_URL"])

r.set('foo', 'bar')
value = r.get('foo')```
the env vars are already configured with the same keys as given in the snippets configured and just load the env vars using load_dotenv(). YOU are strictly prohibited to read from the .env. if absolutely necessary, then use bash to check if the key you're using is empty or has some value, not allowed to read it.

If need be check out the documentation on upstash, we're using redis-py and qstash

Final outcome must be a working pipeline with qstash and redis configured. Tests for setup, and use-cases. must test with the testClient and the test cases before claiming completion

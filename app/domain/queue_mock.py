import os
import sys
import json
import random
from pprint import saferepr

import redis
from termcolor import cprint, colored

if len(sys.argv) == 2:
    REDIS_HOST = sys.argv[1]
else:
    REDIS_HOST = "localhost"

r = redis.StrictRedis(
    host=REDIS_HOST,
    port=6380,  # password="owSuegeP53xb8JCpuSOuCO6T2BMG69U6"
)
pubsub = r.pubsub()
pubsub.psubscribe("*")

logs = []
colors = [
    "red",
    "blue",
    "yellow",
    "green",
]

for message in pubsub.listen():
    os.system("clear")
    logs.append(message)

    for i, log in enumerate(logs, start=1):
        print("%s: %s" % (i, colored(saferepr(log), color=colors[i % 4])))

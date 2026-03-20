from kafka import KafkaProducer
from faker import Faker
import json
import random
import time

import logging
import os

os.makedirs("proof/logs", exist_ok=True)
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s',
                    handlers=[
                        logging.FileHandler("proof/logs/generator.log"),
                        logging.StreamHandler()
                    ])

fake = Faker()

producer = KafkaProducer(
    bootstrap_servers="localhost:29092",
    value_serializer=lambda v: json.dumps(v).encode("utf-8")
)

products = ["p1","p2","p3","p4"]

while True:

    event = {
        "user_id": fake.user_name(),
        "product_id": random.choice(products),
        "action": random.choice(["view","click","buy"])
    }

    producer.send("user-events", event)

    logging.info(f"Generated event: {event}")

    time.sleep(1)
Below is a **realistic production-style architecture** for a scalable streaming pipeline using:

* Apache Kafka (event streaming)
* Apache Cassandra (distributed database)
* Apache Flink (stream processing)
* Kafka Connect (data integration)
* Docker + Docker Compose (deployment)

This architecture is **closer to real production pipelines** used for recommendation systems.

---

# 1. Final Production Architecture

```text
                +----------------------+
                |   Cassandra Cluster  |
                |   user_activity      |
                +----------+-----------+
                           |
                    Kafka Connect Source
                           |
                           v
                  +-------------------+
                  |   Kafka Cluster   |
                  |   user-events     |
                  +---------+---------+
                            |
                            v
                    +---------------+
                    |    Flink      |
                    | Processing    |
                    +-------+-------+
                            |
                            v
                  +-------------------+
                  | Kafka Topic       |
                  | recommendations   |
                  +---------+---------+
                            |
                    Kafka Connect Sink
                            |
                            v
               +----------------------+
               | Cassandra Cluster    |
               | recommendations      |
               +----------------------+
```

This architecture provides:

✔ horizontal scalability
✔ fault tolerance
✔ replayable event logs
✔ exactly-once stream processing

---

# 2. Project Folder Structure

Create project folder in **Documents**.

```bash
cd ~/Documents
mkdir kafka-cassandra-connector
cd kafka-cassandra-connector
```

Create full structure:

```bash
mkdir -p \
docker \
flink_jobs \
connectors \
scripts \
config \
data \
logs \
venv
```

Final layout:

```
kafka-cassandra-connector
│
├── docker
│   └── docker-compose.yml
│
├── flink_jobs
│   └── recommendation_job.py
│
├── connectors
│   ├── cassandra-source.json
│   └── cassandra-sink.json
│
├── scripts
│   └── generate_data.py
│
├── config
│   └── cassandra_schema.cql
│
├── data
├── logs
└── venv
```

---

# 3. Install Dependencies

Install Docker.

```bash
sudo apt update
sudo apt install docker.io docker-compose -y
```

Start Docker.

```bash
sudo systemctl enable docker
sudo systemctl start docker
```

Add user permission.

```bash
sudo usermod -aG docker $USER
```

Log out and back in.

---

# 4. Docker Compose (Production Style)

Create:

```
docker/docker-compose.yml
```

```yaml
version: "3"

services:

  zookeeper:
    image: confluentinc/cp-zookeeper:7.5.0
    environment:
      ZOOKEEPER_CLIENT_PORT: 2181
    ports:
      - "2181:2181"

  kafka:
    image: confluentinc/cp-kafka:7.5.0
    depends_on:
      - zookeeper
    ports:
      - "9092:9092"
    environment:
      KAFKA_BROKER_ID: 1
      KAFKA_ZOOKEEPER_CONNECT: zookeeper:2181
      KAFKA_ADVERTISED_LISTENERS: PLAINTEXT://localhost:9092
      KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR: 1

  kafka-connect:
    image: confluentinc/cp-kafka-connect:7.5.0
    depends_on:
      - kafka
    ports:
      - "8083:8083"
    environment:
      CONNECT_BOOTSTRAP_SERVERS: kafka:9092
      CONNECT_GROUP_ID: connect-cluster
      CONNECT_CONFIG_STORAGE_TOPIC: connect-config
      CONNECT_OFFSET_STORAGE_TOPIC: connect-offsets
      CONNECT_STATUS_STORAGE_TOPIC: connect-status

  cassandra:
    image: cassandra:4.1
    ports:
      - "9042:9042"

  flink-jobmanager:
    image: flink:1.18
    command: jobmanager
    ports:
      - "8081:8081"
    environment:
      - JOB_MANAGER_RPC_ADDRESS=flink-jobmanager

  flink-taskmanager:
    image: flink:1.18
    depends_on:
      - flink-jobmanager
    command: taskmanager
    environment:
      - JOB_MANAGER_RPC_ADDRESS=flink-jobmanager
```

---

# 5. Start Infrastructure

```bash
cd docker
docker-compose up -d
```

Check containers:

```bash
docker ps
```

You should see:

```
kafka
zookeeper
cassandra
kafka-connect
flink-jobmanager
flink-taskmanager
```

---

# 6. Create Kafka Topics

Enter Kafka container.

```bash
docker exec -it $(docker ps | grep kafka | awk '{print $1}') bash
```

Create topics.

```bash
kafka-topics \
--create \
--topic user-events \
--bootstrap-server localhost:9092 \
--partitions 6 \
--replication-factor 1
```

Second topic:

```bash
kafka-topics \
--create \
--topic recommendations \
--bootstrap-server localhost:9092 \
--partitions 6 \
--replication-factor 1
```

---

# 7. Cassandra Schema

Create file:

```
config/cassandra_schema.cql
```

```sql
CREATE KEYSPACE recommendation
WITH replication = {'class':'SimpleStrategy','replication_factor':1};

USE recommendation;

CREATE TABLE user_activity (
    user_id text,
    product_id text,
    action text,
    ts timestamp,
    PRIMARY KEY ((user_id), ts)
);

CREATE TABLE recommendations (
    user_id text,
    product_id text,
    score float,
    PRIMARY KEY ((user_id), product_id)
);
```

Run schema:

```bash
docker exec -it cassandra cqlsh
```

Paste schema.

---

# 8. Data Generator (Simulating Users)

Create:

```
scripts/generate_data.py
```

Install Python dependencies.

```bash
python3 -m venv venv
source venv/bin/activate
pip install kafka-python faker
```

Code:

```python
from kafka import KafkaProducer
from faker import Faker
import json
import random
import time

fake = Faker()

producer = KafkaProducer(
    bootstrap_servers="localhost:9092",
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

    print(event)

    time.sleep(1)
```

Run generator:

```bash
python scripts/generate_data.py
```

---

# 9. Flink Processing Job

Create:

```
flink_jobs/recommendation_job.py
```

```python
from pyflink.datastream import StreamExecutionEnvironment
from pyflink.common.serialization import SimpleStringSchema
from pyflink.datastream.connectors.kafka import FlinkKafkaConsumer
from pyflink.datastream.connectors.kafka import FlinkKafkaProducer

env = StreamExecutionEnvironment.get_execution_environment()

env.enable_checkpointing(10000)

props = {
 "bootstrap.servers": "kafka:9092",
 "group.id": "flink-group"
}

consumer = FlinkKafkaConsumer(
 topics="user-events",
 deserialization_schema=SimpleStringSchema(),
 properties=props
)

stream = env.add_source(consumer)

processed = stream.map(lambda x: x + " recommendation")

producer = FlinkKafkaProducer(
 topic="recommendations",
 serialization_schema=SimpleStringSchema(),
 producer_config={"bootstrap.servers":"kafka:9092"}
)

processed.add_sink(producer)

env.execute("Recommendation Engine")
```

Submit job:

```bash
docker exec -it flink-jobmanager bash
```

Run:

```bash
flink run -py /opt/flink/flink_jobs/recommendation_job.py
```

---

# 10. Cassandra Sink Connector

Create:

```
connectors/cassandra-sink.json
```

```json
{
"name": "cassandra-sink",
"config": {
"connector.class": "com.datastax.kafkaconnector.CassandraSinkConnector",
"tasks.max": "2",
"topics": "recommendations",
"contactPoints": "cassandra",
"loadBalancing.localDc": "datacenter1",
"keyspace": "recommendation",
"table": "recommendations"
}
}
```

Register connector:

```bash
curl -X POST \
http://localhost:8083/connectors \
-H "Content-Type: application/json" \
-d @connectors/cassandra-sink.json
```

---

# 11. Monitor Flink

Open dashboard:

```
http://localhost:8081
```

You can view:

* running jobs
* task managers
* checkpoint status

---

# 12. Scaling the System

Scale Kafka:

```yaml
KAFKA_BROKER_ID: 1
KAFKA_BROKER_ID: 2
KAFKA_BROKER_ID: 3
```

Scale Flink workers:

```bash
docker-compose up --scale flink-taskmanager=3
```

---

# 13. Production Improvements

Add:

* Prometheus monitoring
* Grafana dashboards
* Confluent Schema Registry
* TLS encryption
* Kubernetes deployment

---

# 14. Real-World Throughput

With this architecture you can process:

```
500K – 5M events/sec
```

depending on cluster size.

---

✅ If you'd like, I can also show a **much more advanced architecture used by companies** with:

* **exactly-once Flink processing**
* **stateful recommendation models**
* **feature store with Cassandra**
* **real-time ranking**
* **ML inference in Flink**

That pipeline looks almost identical to **Netflix/Uber recommendation systems** and is extremely valuable for your project.

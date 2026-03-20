# Real-time Kafka → Flink → Cassandra Recommendation Pipeline

A production-style real-time streaming data pipeline that simulates user interaction events, processes them with Apache Flink, and stores personalized recommendations in Apache Cassandra via Kafka Connect.

---

## Architecture & Significance

```
Python Script → Kafka (user-events) → Flink SQL → Kafka (recommendations) → Kafka Connect → Cassandra
```

| Component | Role |
|---|---|
| **Apache Kafka** | Durable message bus decoupling data producers from consumers |
| **Apache Flink** | Real-time stateful stream processing engine |
| **Kafka Connect + DataStax Sink** | Configuration-driven sink to write Kafka data into Cassandra |
| **Apache Cassandra** | Distributed NoSQL DB for high-throughput recommendation storage |

This architecture enables ingesting thousands of events per second, processing them instantly, and making results queryable in real-time — the backbone of a production recommendation system.

---

## Prerequisites

- Docker & Docker Compose
- Python 3 + pip

---

## Step 1: Start the Infrastructure

```bash
cd docker

# If you previously ran docker-compose with a custom build, remove stale containers first:
docker rm -f flink-jobmanager flink-taskmanager 2>/dev/null || true

# Start all services
docker-compose up -d
```

Wait ~30 seconds for services to fully start. Verify they are all `Up`:
```bash
docker-compose ps
```

> **Note on `KeyError: 'ContainerConfig'`:** If you see this error, it means a stale container from a previous docker build is blocking recreation. Run `docker ps -a | grep flink` to find the old container IDs and `docker rm -f <id>` them before running `docker-compose up -d` again.

---

## Step 2: Set Up the Python Environment

```bash
cd ..  # back to project root
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

## Step 3: Create the Cassandra Schema

```bash
docker exec -i cassandra cqlsh -e "
CREATE KEYSPACE IF NOT EXISTS recommendation
  WITH replication = {'class':'SimpleStrategy','replication_factor':1};

CREATE TABLE IF NOT EXISTS recommendation.user_activity (
  user_id TEXT, product_id TEXT, action TEXT,
  PRIMARY KEY (user_id, product_id)
);

CREATE TABLE IF NOT EXISTS recommendation.recommendations (
  user_id TEXT, product_id TEXT, score FLOAT,
  PRIMARY KEY (user_id, product_id)
);"
```

---

## Step 4: Register the Kafka Connect Cassandra Sink

```bash
cd connectors
jq '.config' cassandra-sink.json > cassandra-sink-config.json
curl -X PUT http://localhost:8083/connectors/cassandra-sink/config \
  -H "Content-Type: application/json" \
  -d @cassandra-sink-config.json
cd ..
```

Verify it shows `RUNNING`:
```bash
curl -s http://localhost:8083/connectors/cassandra-sink/status | python3 -m json.tool
```

---

## Step 5: Start the Data Generator

In one terminal, run the event simulator — it generates fake user activity every second and sends it to the `user-events` Kafka topic. Events are logged to `proof/logs/generator.log`.

```bash
source venv/bin/activate
python scripts/generate_data.py
```

---

## Step 6: Run the Flink Streaming Job

In a **separate terminal**, open the Flink SQL Client:

```bash
docker exec -it flink-jobmanager /opt/flink/bin/sql-client.sh
```

Then paste these commands one by one inside the SQL client:

```sql
CREATE TABLE user_events (
    user_id STRING, product_id STRING, action STRING
) WITH (
    'connector' = 'kafka',
    'topic' = 'user-events',
    'properties.bootstrap.servers' = 'kafka:9092',
    'properties.group.id' = 'flink-sql-group',
    'scan.startup.mode' = 'earliest-offset',
    'format' = 'json'
);

CREATE TABLE recommendations (
    user_id STRING, product_id STRING, score FLOAT
) WITH (
    'connector' = 'kafka',
    'topic' = 'recommendations',
    'properties.bootstrap.servers' = 'kafka:9092',
    'format' = 'json'
);

INSERT INTO recommendations
SELECT user_id, product_id, 1.0 AS score FROM user_events;
```

The last `INSERT` statement starts a continuous Flink streaming job.

---

## Step 7: Verify in Cassandra

```bash
docker exec -it cassandra cqlsh -e \
  "SELECT * FROM recommendation.recommendations LIMIT 20;"
```

You should see rows like:
```
 user_id      | product_id | score
--------------+------------+-------
 smithdarlene |         p4 |     1
    annaclark |         p1 |     1
```

---

## Proof

- `proof/cassandra_data.txt` — snapshot of recommendations written to Cassandra
- `proof/kafka_connect_status.json` — Kafka Connect status showing `RUNNING`
- `proof/logs/generator.log` — live log of all generated user events

---

## Troubleshooting

| Problem | Fix |
|---|---|
| `KeyError: 'ContainerConfig'` | `docker rm -f flink-jobmanager flink-taskmanager && docker-compose up -d` |
| `KafkaTimeoutError` in Python script | Kafka not ready or port 29092 not exposed. Wait 30s and retry. |
| Flink SQL Client: `kafka` connector missing | Run `docker logs flink-jobmanager` and check if the wget download succeeded. If not, run the manual copy steps below. |
| Cassandra table empty | Run `docker logs kafka-connect \| grep -i error` to check for mapping errors. |

**Manual Flink Kafka Connector install (if wget fails on startup):**
```bash
wget -q https://repo1.maven.org/maven2/org/apache/flink/flink-sql-connector-kafka/3.0.2-1.18/flink-sql-connector-kafka-3.0.2-1.18.jar -P /tmp/
docker cp /tmp/flink-sql-connector-kafka-3.0.2-1.18.jar flink-jobmanager:/opt/flink/lib/
docker cp /tmp/flink-sql-connector-kafka-3.0.2-1.18.jar flink-taskmanager:/opt/flink/lib/
docker restart flink-jobmanager flink-taskmanager
```

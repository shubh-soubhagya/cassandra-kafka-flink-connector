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
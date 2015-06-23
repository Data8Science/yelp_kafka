import subprocess
import uuid
import time

import kafka

from yelp_kafka.config import ClusterConfig, KafkaConsumerConfig
from yelp_kafka.consumer import KafkaSimpleConsumer
from yelp_kafka.consumer_group import KafkaConsumerGroup


ZOOKEEPER_URL = 'zookeeper:2181'
KAFKA_URL = 'kafka:9092'


def create_topic(topic_name, replication_factor, partitions):
    cmd = ['/usr/bin/kafka-topics', '--create',
           '--zookeeper', ZOOKEEPER_URL,
           '--replication-factor', str(replication_factor),
           '--partitions', str(partitions),
           '--topic', topic_name]
    subprocess.check_call(cmd)

    # It may take a little moment for the topic to be ready for writing.
    time.sleep(1)


def create_random_topic(replication_factor, partitions):
    topic_name = str(uuid.uuid1())
    create_topic(topic_name, replication_factor, partitions)
    return topic_name


def test_simple_consumer():
    topic = create_random_topic(1, 1)

    messages = [str(i) for i in range(100)]

    producer = kafka.SimpleProducer(kafka.KafkaClient(KAFKA_URL))
    producer.send_messages(topic, *messages)

    cluster_config = ClusterConfig(None, [KAFKA_URL], ZOOKEEPER_URL)
    config = KafkaConsumerConfig('test', cluster_config,
                                 auto_offset_reset='smallest')
    consumer = KafkaSimpleConsumer(topic, config)

    with consumer:
        for expected_offset in xrange(100):
            message = consumer.get_message()
            assert message.offset == expected_offset
            assert message.partition == 0
            assert message.value == str(expected_offset)


def test_kafka_consumer_group_one_partition():
    run_kafka_consumer_group_test(1)


def test_kafka_consumer_group_two_partitions():
    run_kafka_consumer_group_test(2)


def run_kafka_consumer_group_test(num_partitions):
    sent_messages = [str(i) for i in range(100)]

    producer = kafka.SimpleProducer(kafka.KafkaClient(KAFKA_URL))

    cluster_config = ClusterConfig(None, [KAFKA_URL], ZOOKEEPER_URL)
    config = KafkaConsumerConfig('test', cluster_config,
                                 auto_offset_reset='smallest')

    topic = create_random_topic(1, num_partitions)
    producer.send_messages(topic, *sent_messages)

    consumer = KafkaConsumerGroup([topic], config)
    with consumer:
        # If we don't get any exceptions here, we're good.
        for _ in xrange(100):
            consumer.next()

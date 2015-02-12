# -*- coding: utf-8 -*-

import contextlib
from collections import namedtuple

import kafka
import mock
import yelp_kafka

KafkaMocks = namedtuple(
    'KafkaMocks',
    [
        'KafkaClient',
        'SimpleProducer',
        'KeyedProducer',
        'SimpleConsumer',
        'KafkaSimpleConsumer',
    ],
)


class Registrar(object):
    def __init__(self):
        self.topic_registry = {}

    def mock_producer_with_registry(self):

        class MockProducer(object):
            ACK_AFTER_CLUSTER_COMMIT = 2

            def __init__(
                inner_self,
                client,
                async=False,
                req_acks=1,
                ack_timeout=1000,
                codec=None,
                batch_send=False,
                batch_send_every_n=20,
                batch_send_every_t=20,
                random_start=False
            ):
                inner_self._client = client

            def send_messages(inner_self, topic, *messages):
                # inner_self so we can address the parent object Registrar
                # with self, thus accessing global test state.
                topic_list = self.topic_registry.setdefault(topic, [])
                current_offset = len(topic_list)
                new_messages = [
                    kafka.common.OffsetAndMessage(
                        offset=i + current_offset,
                        message=kafka.common.Message(
                            magic=0,
                            attributes=0,
                            key=None,
                            value=msg,
                        )
                    ) for i, msg in enumerate(messages)]
                topic_list.extend(new_messages)

        return MockProducer

    def mock_keyed_producer_with_registry(self):
        class MockKeyedProducer(object):
            ACK_AFTER_CLUSTER_COMMIT = 2

            def __init__(
                inner_self,
                client,
                async=False,
                req_acks=1,
                ack_timeout=1000,
                codec=None,
                batch_send=False,
                batch_send_every_n=20,
                batch_send_every_t=20,
                random_start=False
            ):
                inner_self._client = client
                self._client = client

            def send_messages(inner_self, topic, key, *messages):
                # XXX: By default, don't support multiple partitions in the
                # mock. If we need testing support for this, add it later.

                # inner_self so we can address the parent object Registrar
                # with self, thus accessing global test state.
                topic_list = self.topic_registry.setdefault(topic, [])
                current_offset = len(topic_list)
                new_messages = [
                    kafka.common.OffsetAndMessage(
                        offset=i + current_offset,
                        message=kafka.common.Message(
                            magic=0,
                            attributes=0,
                            key=key,
                            value=msg,
                        )
                    ) for i, msg in enumerate(messages)]
                topic_list.extend(new_messages)

        return MockKeyedProducer

    def mock_consumer_with_registrar(self):
        class MockConsumer(object):
            """I personally don't need this to be super hardcore, but anyone who
            wants to, feel free to add auto_commit and fetch_last_known_offset
            support."""
            def __init__(
                inner_self,
                client,
                group,
                topic,
                auto_commit=True,
                partitions=None,
                auto_commit_every_n=100,
                auto_commit_every_t=5000,
                fetch_size_bytes=4096,
                buffer_size=4096,
                max_buffer_size=32768,
                iter_timeout=None
            ):
                # XXX: This just snapshots the current topic. New messages produced
                # won't make it into here.If you need this, build it :)
                inner_self._topic = list(self.topic_registry.get(topic, []))
                inner_self._offset = 0

            def get_messages(inner_self, count=1, block=True, timeout=0.10000000000000001):
                # inner_self so we can address the parent object Registrar
                # with self, thus accessing global test state.
                new_offset = min(inner_self._offset + count, len(inner_self._topic))
                old_offset = inner_self._offset
                inner_self._offset = new_offset
                return inner_self._topic[old_offset:new_offset]

            def get_message(inner_self, block=True, timeout=0.1, get_partition_info=None):
                return inner_self.get_messages(count=1, block=block, timeout=timeout)[0]

            def commit(inner_self, partitions=None):
                pass

            def fetch_last_known_offsets(inner_self, partitions=None):
                return [inner_self._offset]

            def seek(inner_self, offset, whence):
                pass

            def __iter__(inner_self):
                for msg in inner_self._topic[inner_self._offset:]:
                    yield msg

        return MockConsumer

    def mock_yelp_consumer_with_registrar(self):
        class MockConsumer(object):
            def __init__(
                inner_self,
                topic,
                config,
                partitions=None,
            ):
                # XXX: This just snapshots the current topic. New messages produced
                # won't make it into here.If you need this, build it :)
                inner_self._topic = list(self.topic_registry.get(topic, []))
                inner_self._offset = 0

            def connect(self):
                pass

            def _translate_messages_to_yelp(inner_self, messages):
                return [yelp_kafka.consumer.Message(
                    partition=0,
                    offset=message.offset,
                    key=message.message.key,
                    value=message.message.value,
                ) for message in messages]

            def get_messages(inner_self, count=1, block=True, timeout=0.10000000000000001):
                # inner_self so we can address the parent object Registrar
                # with self, thus accessing global test state.
                new_offset = min(inner_self._offset + count, len(inner_self._topic))
                old_offset = inner_self._offset
                inner_self._offset = new_offset

                return inner_self._translate_messages_to_yelp(
                    inner_self._topic[old_offset:new_offset]
                )

            def get_message(inner_self, block=True, timeout=0.1, get_partition_info=None):
                return inner_self.get_messages(
                    count=1,
                    block=block,
                    timeout=timeout,
                )[0]

            def close(self):
                pass

            def __iter__(inner_self):
                translated_messages = inner_self._translate_messages_to_yelp(
                    inner_self._topic[inner_self._offset:],
                )
                for msg in translated_messages:
                    yield msg

        return MockConsumer


@contextlib.contextmanager
def mock_kafka_python():
    registrar = Registrar()
    with contextlib.nested(
        mock.patch.object(kafka, 'KafkaClient', autospec=True),
        mock.patch.object(kafka, 'SimpleProducer', registrar.mock_producer_with_registry()),
        mock.patch.object(kafka, 'KeyedProducer', registrar.mock_keyed_producer_with_registry()),
        mock.patch.object(kafka, 'SimpleConsumer', registrar.mock_consumer_with_registrar()),
        mock.patch.object(yelp_kafka.consumer, 'KafkaSimpleConsumer', registrar.mock_yelp_consumer_with_registrar()),
    ) as (Client, Producer, KeyedProducer, Consumer, YelpConsumer):
        yield KafkaMocks(
            KafkaClient=Client,
            SimpleProducer=Producer,
            KeyedProducer=KeyedProducer,
            SimpleConsumer=Consumer,
            KafkaSimpleConsumer=YelpConsumer,
        )
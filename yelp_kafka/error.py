# -*- coding: utf-8 -*-
from __future__ import absolute_import
from __future__ import unicode_literals


class YelpKafkaError(Exception):
    """Base class for yelp_kafka errors."""
    pass


class DiscoveryError(YelpKafkaError):
    """Errors while using discovery functions."""
    pass


class ConsumerError(YelpKafkaError):
    """Error in consumer."""
    pass


class ConfigurationError(YelpKafkaError):
    """Error in configuration. For example. Missing configuration file
    or misformatted configuration."""
    pass


class InvalidOffsetStorageError(YelpKafkaError):
    """Unknown source of offsets."""
    pass


class ProcessMessageError(YelpKafkaError):
    """Error processing a message from kafka."""
    pass


class ConsumerGroupError(YelpKafkaError):
    """Error in the consumer group"""
    pass


class PartitionerError(YelpKafkaError):
    """Error in the partitioner"""
    pass


class PartitionerZookeeperError(YelpKafkaError):
    """Error in partitioner communication with Zookeeper"""
    pass


class UnknownTopic(YelpKafkaError):
    pass


class UnknownPartitions(YelpKafkaError):
    pass


class OffsetCommitError(YelpKafkaError):

    def __init__(self, topic, partition, error):
        self.topic = topic
        self.partition = partition
        self.error = error

    def __eq__(self, other):
        if all([
            self.topic == other.topic,
            self.partition == other.partition,
            self.error == other.error,
        ]):
            return True
        return False


class InvalidClusterTypeOrRegionError(YelpKafkaError):
    pass


class InvalidClusterTypeOrNameError(YelpKafkaError):
    pass


class InvalidClusterTypeOrSuperregionError(YelpKafkaError):
    pass


class InvalidClusterType(YelpKafkaError):
    pass


class InvalidLogOrRegionError(YelpKafkaError):
    pass


class InvalidLogOrSuperregionError(YelpKafkaError):
    pass

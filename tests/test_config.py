import contextlib
import mock
import pytest
from StringIO import StringIO

from kafka.consumer.kafka import DEFAULT_CONSUMER_CONFIG

from yelp_kafka.config import (
    MAX_MESSAGE_SIZE_BYTES,
    AUTO_COMMIT_INTERVAL_SECS,
    ClusterConfig,
    KafkaConsumerConfig,
    load_yaml_config,
    TopologyConfiguration,
)
from yelp_kafka.error import ConfigurationError

TEST_BASE_KAFKA = '/base/kafka_discovery'

MOCK_TOPOLOGY_CONFIG = """
---
  clusters:
    cluster1:
      broker_list:
        - "mybrokerhost1:9092"
      zookeeper: "0.1.2.3,0.2.3.4/kafka"
    cluster2:
      broker_list:
        - "mybrokerhost2:9092"
      zookeeper: "0.3.4.5,0.4.5.6/kafka"
  local_config:
    cluster: cluster1
    prefix: my.prefix.
"""

MOCK_SCRIBE_YAML = {
    'clusters': {
        'cluster1': {
            'broker_list': ["mybrokerhost1:9092"],
            'zookeeper': "0.1.2.3,0.2.3.4/kafka"
        },
        'cluster2': {
            'broker_list': ["mybrokerhost2:9092"],
            'zookeeper': "0.3.4.5,0.4.5.6/kafka"
        }
    },
    'local_config': {
        'cluster': 'cluster1',
        'prefix': 'my.prefix.'
    }
}

MOCK_SCRIBE_YAML_2 = {
    'clusters': {
        'uswest2-prod': {
            'broker_list': ["mybrokerhost1-uswest2-prod:9092"],
            'zookeeper': "0.1.2.3,0.2.3.4/kafka"
        },
        'sfo12-prod': {
            'broker_list': ["mybrokerhost1-sfo12-prod:9092"],
            'zookeeper': "0.1.2.3,0.2.3.4/kafka"
        },
        'useast1-prod': {
            'broker_list': ["mybrokerhost1-useast1-prod:9092"],
            'zookeeper': "0.5.6.7,0.8.9.1/kafka"
        },
        'dc6-prod': {
            'broker_list': ["mybrokerhost1-dc6-prod:9092"],
            'zookeeper': "0.5.6.7,0.8.9.1/kafka"
        }
    },
    'local_config': {
        'cluster': 'uswest2-prod',
        'prefix': 'my.prefix.'
    }
}

MOCK_SCRIBE_YAML_3 = {
    'clusters': {
        'uswest2-prod': {
            'broker_list': ["mybrokerhost1-uswest2-prod:9092"],
            'zookeeper': "0.1.2.3,0.2.3.4/kafka"
        },
        'useast1-prod': {
            'broker_list': ["mybrokerhost1-useast1-prod:9092"],
            'zookeeper': "0.5.6.7,0.8.9.1/kafka"
        },
    },
    'local_config': {
        'cluster': 'uswest2-prod',
        'prefix': 'my.prefix.'
    }
}

MOCK_NO_SCRIBE_YAML = {
    'clusters': {
        'cluster1': {
            'broker_list': ["mybrokerhost1:9092"],
            'zookeeper': "0.1.2.3,0.2.3.4/kafka"
        },
        'cluster2': {
            'broker_list': ["mybrokerhost2:9092"],
            'zookeeper': "0.3.4.5,0.4.5.6/kafka"
        }
    },
    'local_config': {
        'cluster': 'cluster1',
    }
}


class TestClusterConfig():
    def test___eq___broker_list(self):
        cluster_config1 = ClusterConfig(
            type='some_type',
            name='some_cluster',
            broker_list=['kafka-cluster-1:9092', 'kafka-cluster-2:9092'],
            zookeeper='zookeeper-cluster-1:2181,zookeeper-cluster-2:2181,'
        )
        cluster_config2 = ClusterConfig(
            type='some_type',
            name='some_cluster',
            broker_list=['kafka-cluster-1:9092', 'kafka-cluster-2:9092'],
            zookeeper='zookeeper-cluster-1:2181,zookeeper-cluster-2:2181,'
        )
        assert cluster_config1 == cluster_config2
        # Re-ordering the list of brokers
        cluster_config2 = ClusterConfig(
            type='some_type',
            name='some_cluster',
            broker_list=['kafka-cluster-2:9092', 'kafka-cluster-1:9092'],
            zookeeper='zookeeper-cluster-1:2181,zookeeper-cluster-2:2181,'
        )
        assert cluster_config1 == cluster_config2

    def test___eq___broker_str(self):
        cluster_config1 = ClusterConfig(
            type='some_type',
            name='some_cluster',
            broker_list='kafka-cluster-1:9092,kafka-cluster-2:9092',
            zookeeper='zookeeper-cluster-1:2181,zookeeper-cluster-2:2181,'
        )
        cluster_config2 = ClusterConfig(
            type='some_type',
            name='some_cluster',
            broker_list='kafka-cluster-1:9092,kafka-cluster-2:9092',
            zookeeper='zookeeper-cluster-1:2181,zookeeper-cluster-2:2181,'
        )
        assert cluster_config1 == cluster_config2
        # Re-order the comma separated pair of brokers and zookeeper nodes
        cluster_config2 = ClusterConfig(
            type='some_type',
            name='some_cluster',
            broker_list='kafka-cluster-2:9092,kafka-cluster-1:9092',
            zookeeper='zookeeper-cluster-2:2181,zookeeper-cluster-1:2181,'
        )
        assert cluster_config1 == cluster_config2

    def test___ne___broker_str(self):
        cluster_config1 = ClusterConfig(
            type='some_type',
            name='some_cluster',
            broker_list='kafka-cluster-1:9092,kafka-cluster-2:9092',
            zookeeper='zookeeper-cluster-1:2181,zookeeper-cluster-2:2181,'
        )
        # Different comma separated pair of brokers
        cluster_config2 = ClusterConfig(
            type='some_type',
            name='some_cluster',
            broker_list='kafka-cluster-2:9092,kafka-cluster-3:9092',
            zookeeper='zookeeper-cluster-1:2181,zookeeper-cluster-2:2181,'
        )
        assert cluster_config1 != cluster_config2
        # Different comma separated pair of zookeeper nodes
        cluster_config2 = ClusterConfig(
            type='some_type',
            name='some_cluster',
            broker_list='kafka-cluster-1:9092,kafka-cluster-2:9092',
            zookeeper='zookeeper-cluster-2:2181,zookeeper-cluster-3:2181,'
        )
        assert cluster_config1 != cluster_config2

    def test___ne___broker_list(self):
        cluster_config1 = ClusterConfig(
            type='some_type',
            name='some_cluster',
            broker_list=['kafka-cluster-1:9092', 'kafka-cluster-2:9092'],
            zookeeper='zookeeper-cluster-1:2181,zookeeper-cluster-2:2181,'
        )
        # Different broker list
        cluster_config2 = ClusterConfig(
            type='some_type',
            name='some_cluster',
            broker_list=['kafka-cluster-1:9092', 'kafka-cluster-3:9092'],
            zookeeper='zookeeper-cluster-1:2181,zookeeper-cluster-2:2181,'
        )
        assert cluster_config1 != cluster_config2


@pytest.yield_fixture
def mock_yaml():
    with contextlib.nested(
        mock.patch('yelp_kafka.config.load_yaml_config',
                   return_value=MOCK_SCRIBE_YAML,
                   create=True),
        mock.patch('os.path.isfile', return_value=True)
    ) as (m, mock_isfile):
        yield m


def test_load_yaml():
    stio = StringIO()
    stio.write(MOCK_TOPOLOGY_CONFIG)
    stio.seek(0)
    with mock.patch('__builtin__.open',
                    return_value=contextlib.closing(stio)) as mock_open:
        actual = load_yaml_config('test')
        mock_open.assert_called_once_with("test", "r")
        assert actual == MOCK_SCRIBE_YAML


class TestTopologyConfig(object):

    def test_missing_cluster(self):
        with pytest.raises(ConfigurationError):
            with mock.patch("os.path.isfile", return_value=False):
                TopologyConfiguration(
                    cluster_type="wrong_cluster",
                    kafka_topology_path=TEST_BASE_KAFKA
                )

    def test_get_local_cluster(self, mock_yaml):
        topology = TopologyConfiguration(
            cluster_type='mykafka',
            kafka_topology_path=TEST_BASE_KAFKA,
        )
        mock_yaml.assert_called_once_with('/base/kafka_discovery/mykafka.yaml')
        actual_cluster = topology.get_local_cluster()
        expected_cluster = ClusterConfig(
            'mykafka',
            'cluster1',
            ['mybrokerhost1:9092'],
            '0.1.2.3,0.2.3.4/kafka',
        )
        assert actual_cluster == expected_cluster

    def test_get_local_cluster_error(self, mock_yaml):
        # Should raise ConfigurationError if a cluster is in region but not in
        # the cluster list
            mock_yaml.return_value = {
                'clusters': {
                    'cluster1': {
                        'broker_list': ['mybroker'],
                        'zookeeper': '0.1.2.3,0.2.3.4/kafka'
                    },
                },
                'local_config': {
                    'cluster': 'cluster3'
                }
            }
            topology = TopologyConfiguration(
                cluster_type='mykafka',
                kafka_topology_path=TEST_BASE_KAFKA,
            )
            # Raise ConfigurationError because cluster 3 does not exist
            with pytest.raises(ConfigurationError):
                topology.get_local_cluster()

    def test_get_scribe_prefix(self, mock_yaml):
        topology = TopologyConfiguration(
            cluster_type='mykafka',
            kafka_topology_path=TEST_BASE_KAFKA,
        )
        assert 'my.prefix.' == topology.get_scribe_local_prefix()

    def test_get_scribe_prefix_None(self, mock_yaml):
        mock_yaml.return_value = MOCK_NO_SCRIBE_YAML
        topology = TopologyConfiguration(
            cluster_type='mykafka',
            kafka_topology_path=TEST_BASE_KAFKA,
        )
        assert not topology.get_scribe_local_prefix()

    def test_get_all_clusters(self, mock_yaml):
        topology = TopologyConfiguration(
            cluster_type='mykafka',
            kafka_topology_path=TEST_BASE_KAFKA,
        )
        actual_clusters = topology.get_all_clusters()
        expected_clusters = [
            ClusterConfig(
                'mykafka', 'cluster1', ["mybrokerhost1:9092"], "0.1.2.3,0.2.3.4/kafka"
            ),
            ClusterConfig(
                'mykafka', 'cluster2', ["mybrokerhost2:9092"], "0.3.4.5,0.4.5.6/kafka"
            )
        ]
        assert sorted(expected_clusters) == sorted(actual_clusters)

    def test_get_all_clusters_exclude_blacklist(self, mock_yaml):
        mock_yaml.return_value = MOCK_SCRIBE_YAML_2
        topology = TopologyConfiguration(
            cluster_type='scribe',
            kafka_topology_path=TEST_BASE_KAFKA,
        )

        actual = topology.get_all_clusters()

        assert sorted(actual) == sorted([
            ClusterConfig(
                'scribe',
                'sfo12-prod',
                ["mybrokerhost1-sfo12-prod:9092"],
                "0.1.2.3,0.2.3.4/kafka",
            ),
            ClusterConfig(
                'scribe',
                'dc6-prod',
                ["mybrokerhost1-dc6-prod:9092"],
                "0.5.6.7,0.8.9.1/kafka",
            )
        ])

    def test_get_all_clusters_empty_blacklist(self, mock_yaml):
        mock_yaml.return_value = MOCK_SCRIBE_YAML_3
        topology = TopologyConfiguration(
            cluster_type='scribe',
            kafka_topology_path=TEST_BASE_KAFKA,
        )

        actual = topology.get_all_clusters()

        assert sorted(actual) == sorted([
            ClusterConfig(
                'scribe',
                'uswest2-prod',
                ["mybrokerhost1-uswest2-prod:9092"],
                "0.1.2.3,0.2.3.4/kafka",
            ),
            ClusterConfig(
                'scribe',
                'useast1-prod',
                ["mybrokerhost1-useast1-prod:9092"],
                "0.5.6.7,0.8.9.1/kafka",
            )
        ])

    def test_get_cluster_by_name(self, mock_yaml):
        topology = TopologyConfiguration(
            cluster_type='mykafka',
            kafka_topology_path=TEST_BASE_KAFKA,
        )
        actual_cluster = topology.get_cluster_by_name('cluster1')
        expected_cluster = ClusterConfig(
            'mykafka', 'cluster1', ["mybrokerhost1:9092"], "0.1.2.3,0.2.3.4/kafka"
        )
        assert expected_cluster == actual_cluster

        with pytest.raises(ConfigurationError):
            topology.get_cluster_by_name('does-not-exist')

    def test___eq__(self):
        topology1 = TopologyConfiguration("standard", "/nail/etc/kafka_discovery")
        topology2 = TopologyConfiguration("standard", "/nail/etc/kafka_discovery")
        assert topology1 == topology2

        topology1 = TopologyConfiguration("scribe")
        topology2 = TopologyConfiguration("scribe")
        assert topology1 == topology2

    def test___ne__(self):
        topology1 = TopologyConfiguration("standard", "/nail/etc/kafka_discovery")
        topology2 = TopologyConfiguration("scribe", "/nail/etc/kafka_discovery")
        assert topology1 != topology2

        topology1 = TopologyConfiguration("standard")
        topology2 = TopologyConfiguration("spam")
        assert topology1 != topology2


class TestKafkaConsumerConfig(object):
    def test___eq__(self):
        consumer_config = {
            'buffer_size': 1024,
            'auto_commit_every_n': 100,
            'auto_commit_every_t': 20,
            'auto_commit': True,
            'fetch_size_bytes': 4096,
            'max_buffer_size': None,
            'iter_timeout': 120,
        }
        cluster_config = ClusterConfig(
            type='mykafka',
            name='some_cluster',
            broker_list=['kafka-cluster-1:9092', 'kafka-cluster-2:9092'],
            zookeeper='zookeeper-cluster-1:2181,zookeeper-cluster-2:2181,'
        )

        # Re-ordered consumer config dict
        consumer_config_reordered = {
            'fetch_size_bytes': 4096,
            'auto_commit_every_t': 20,
            'auto_commit': True,
            'max_buffer_size': None,
            'buffer_size': 1024,
            'iter_timeout': 120,
            'auto_commit_every_n': 100,
        }
        cluster_config_reordered = ClusterConfig(
            type='mykafka',
            name='some_cluster',
            broker_list=['kafka-cluster-2:9092', 'kafka-cluster-1:9092'],
            zookeeper='zookeeper-cluster-1:2181,zookeeper-cluster-2:2181,'
        )

        config1 = KafkaConsumerConfig(
            "some_group",
            cluster_config,
            **consumer_config)
        config2 = KafkaConsumerConfig(
            "some_group",
            cluster_config,
            **consumer_config
        )
        assert config1 == config2

        # Let's use a re-ordered map with the same config
        config2 = KafkaConsumerConfig(
            "some_group",
            cluster_config_reordered,
            **consumer_config_reordered
        )
        assert config1 == config2

    def test___ne__(self):
        consumer_config = {
            'buffer_size': 1024,
            'auto_commit_every_n': 100,
            'auto_commit_every_t': 20,
            'auto_commit': True,
            'fetch_size_bytes': 4096,
            'max_buffer_size': None,
            'iter_timeout': 120,
        }
        cluster_config = ClusterConfig(
            type='mykafka',
            name='some_cluster',
            broker_list=['kafka-cluster-1:9092', 'kafka-cluster-2:9092'],
            zookeeper='zookeeper-cluster-1:2181,zookeeper-cluster-2:2181,'
        )

        consumer_config_1 = {
            'fetch_size_bytes': 496,
            'auto_commit_every_t': 20,
            'auto_commit': True,
            'max_buffer_size': None,
            'buffer_size': 104,
            'iter_timeout': 12,
            'auto_commit_every_n': 10,
        }
        cluster_config_1 = ClusterConfig(
            type='mykafka',
            name='some_cluster',
            broker_list=['kafka-cluster-4:9092', 'kafka-cluster-1:9092'],
            zookeeper='zookeeper-cluster-1:2181,zookeeper-cluster-2:2181,'
        )

        # Different cluster config
        config1 = KafkaConsumerConfig(
            "some_group",
            cluster_config,
            **consumer_config
        )
        config2 = KafkaConsumerConfig(
            "some_group",
            cluster_config_1,
            **consumer_config
        )
        assert config1 != config2

        # Different consumer config
        config1 = KafkaConsumerConfig(
            "some_group",
            cluster_config,
            **consumer_config
        )
        config2 = KafkaConsumerConfig(
            "some_group",
            cluster_config,
            **consumer_config_1
        )
        assert config1 != config2

        # Different group ID
        config1 = KafkaConsumerConfig(
            "some_group1",
            cluster_config,
            **consumer_config
        )
        config2 = KafkaConsumerConfig(
            "some_group2",
            cluster_config,
            **consumer_config
        )
        assert config1 != config2

    def test_get_simple_consumer_args(self):
        cluster_config = ClusterConfig(
            type='mykafka',
            name='some_cluster',
            broker_list=['kafka:9092'],
            zookeeper='zookeeper:2181'
        )

        config = KafkaConsumerConfig('some_group',
                                     cluster_config,
                                     auto_offset_reset='smallest',
                                     fetch_min_bytes=456,
                                     consumer_timeout_ms=5000)
        args = config.get_simple_consumer_args()

        assert args['buffer_size'] == MAX_MESSAGE_SIZE_BYTES
        assert args['auto_commit']
        assert args['auto_offset_reset'] == 'smallest'
        assert args['fetch_size_bytes'] == 456
        assert args['iter_timeout'] == 5

    def test_get_kafka_consumer_config(self):
        cluster_config = ClusterConfig(
            type='mykafka',
            name='some_cluster',
            broker_list=['kafka:9092'],
            zookeeper='zookeeper:2181'
        )

        config = KafkaConsumerConfig('some_group',
                                     cluster_config,
                                     fetch_message_max_bytes=123,
                                     auto_commit=False,
                                     iter_timeout=5)
        kafka_config = config.get_kafka_consumer_config()

        assert kafka_config['fetch_message_max_bytes'] == 123
        assert kafka_config['auto_commit_enable'] is False
        assert kafka_config['auto_commit_interval_ms'] == AUTO_COMMIT_INTERVAL_SECS * 1000
        assert kafka_config['socket_timeout_ms'] == DEFAULT_CONSUMER_CONFIG['socket_timeout_ms']
        assert kafka_config['consumer_timeout_ms'] == 5000

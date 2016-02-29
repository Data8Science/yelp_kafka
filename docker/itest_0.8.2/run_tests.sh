#!/bin/bash

set -e

function do_at_exit {
  exit_status=$?
  rm -rf build/ dist/ yelp_kafka.egg-info/
  rm -rf .tox/log .tox/dist
  find . -name '*.pyc' -delete
  find . -name '__pycache__' -delete
  exit $exit_status
}

# Clean up artifacts from tests
trap do_at_exit EXIT INT TERM

tox -e integration

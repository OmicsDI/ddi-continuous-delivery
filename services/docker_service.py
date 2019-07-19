import logging
import os
import subprocess

from services import command_service

DOCKER_BINARY_PATH = 'docker'
logger = logging.getLogger(__name__)
DOCKER_HUB_USER = os.environ['DOCKER_HUB_USER']
DOCKER_HUB_PASSWORD = os.environ['DOCKER_HUB_PASSWORD']


def build_image(tag_name, docker_file='Dockerfile', args='', base_dir='.'):
    logger.info("Starting to build %s, %s, %s", tag_name, docker_file, args)
    params = ['cd', base_dir, '&&', DOCKER_BINARY_PATH, 'build', '-t', tag_name, '-f', docker_file, args, '--quiet', '.']
    command_service.run(params)


def push_image(tag_name):
    logger.info("Pushing image to docker hub %s", tag_name)
    subprocess.run([DOCKER_BINARY_PATH, 'login', '-u', DOCKER_HUB_USER, '-p', DOCKER_HUB_PASSWORD])
    subprocess.run([DOCKER_BINARY_PATH, 'push', tag_name])
    subprocess.run([DOCKER_BINARY_PATH, 'tag', tag_name, 'latest'])
    subprocess.run([DOCKER_BINARY_PATH, 'push', 'latest'])

import logging
import os
from os.path import join

from services import command_service

KUBERNETES_BINARY = 'kubectl'
logger = logging.getLogger(__name__)


def deploy_kubernetes(environment, tag_name, k8s_dir='k8s', base_dir=''):
    logger.info("Deploying docker image %s, %s", environment, tag_name)
    command_service.run([KUBERNETES_BINARY, 'get', 'ns', environment, '||', KUBERNETES_BINARY,
                         'create', 'ns', environment])
    final_dir = join(base_dir, k8s_dir)
    if not os.path.isdir(final_dir):
        logger.info('No k8s folder exist, Ignoring deployment')
        return
    for filename in os.listdir(final_dir):
        if filename.endswith("%s.yaml" % environment):
            file_path = join(final_dir, filename)
            command_service.run(['sed', '-i', "'s#omicsdi.dev.01#%s#g'" % tag_name, file_path])
            command_service.run([KUBERNETES_BINARY, "--namespace=%s" % environment, 'apply', '-f', file_path])


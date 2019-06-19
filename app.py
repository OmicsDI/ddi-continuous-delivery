import hashlib
import hmac
import logging
import os
from ipaddress import ip_network, ip_address
from json import dumps
from sys import hexversion
from celery import Celery

import requests
from flask import Flask, abort, request

from services import k8s_service
from services.docker_service import build_image, push_image
from services.git_service import checkout_code

application = Flask(__name__)
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
branches_to_deploy = ["dev", "prod"]
CHECKOUT_DIR = 'sources'
if 'CHECKOUT_DIR' in os.environ:
    CHECKOUT_DIR = os.environ['CHECKOUT_DIR']

application.config['CELERY_BROKER_URL'] = "redis://%s:%s/0" % (os.environ['REDIS_ENDPOINT'], os.environ['REDIS_PORT'])
application.config['CELERY_RESULT_BACKEND'] = application.config['CELERY_BROKER_URL']

celery = Celery(application.name, broker=application.config['CELERY_BROKER_URL'])
celery.conf.update(application.config)


@celery.task
def run_async_frontend_task(arg):
    build_frontend(arg)


@celery.task
def run_async_generic_task(arg):
    build_generic(arg)


def get_environment(request_body):
    return request_body['pull_request']['base']['ref']


def verify_request():

    # Only POST is implemented
    if request.method != 'POST':
        abort(501)

    # Allow Github IPs only
    src_ip = ip_address(
        u'{}'.format(request.access_route[0])  # Fix stupid ipaddress issue
    )
    logger.info("Getting request from %s" % src_ip)
    logger.info("Headers %s" % request.headers)
    # whitelist = requests.get('https://api.github.com/meta').json()['hooks']
    #
    # for valid_ip in whitelist:
    #     if src_ip in ip_network(valid_ip):
    #         break
    # else:
    #     logging.error('IP {} not allowed'.format(
    #         src_ip
    #     ))
    #     abort(403)

    # Enforce secret
    secret = os.environ['SECRET_TOKEN']
    if secret:
        # Only SHA1 is supported
        header_signature = request.headers.get('X-Hub-Signature')
        if header_signature is None:
            abort(403)

        sha_name, signature = header_signature.split('=')
        if sha_name != 'sha1':
            abort(501)

        # HMAC requires the key to be bytes, but data is string
        mac = hmac.new(str(secret).encode('UTF-8'), request.data, hashlib.sha1)

        # Python prior to 2.7.7 does not have hmac.compare_digest
        if hexversion >= 0x020707F0:
            if not hmac.compare_digest(str(mac.hexdigest()), str(signature)):
                logger.info('hmac comparing failed!!!')
                abort(403)
        else:
            # What compare_digest provides is protection against timing
            # attacks; we can live without this protection for a web-based
            # application
            if not str(mac.hexdigest()) == str(signature):
                logger.info('hmac comparing failed!!!')
                abort(403)
    data = request.get_json()
    if 'pull_request' not in data:
        logger.info('Not pull request\'s type')
        abort(403)
    if data['action'] != 'closed':
        logger.info('Pull request haven\' merged')
        abort(403)
    if not data['pull_request']['merged']:
        logger.info('Pull request haven\' merged')
        abort(403)
    logger.info("Passed verifying request")

    env = get_environment(data)
    if env not in branches_to_deploy:
        logger.info('Branch %s is not suppose to be built');
        abort(403)


def build_frontend(request_body):
    logger.info("Starting to build frontend...")
    env = get_environment(request_body)
    img_tag = "omicsdi.%s.%d" % (env, request_body['pull_request']['id'])
    frontend_tag = 'omicsdi/omicsdi-frontend:' + img_tag
    source_dir = os.path.join(CHECKOUT_DIR, 'omicsdi-frontend')

    # checkout_code(request_body['repository']['clone_url'], source_dir, 'origin/features/cloud-migration')
    logger.info("Checking out %s:%s" % (request_body['repository']['clone_url'],
                                        request_body['pull_request']['base']['ref']))
    checkout_code(request_body['repository']['clone_url'], source_dir, request_body['pull_request']['base']['ref'])

    build_image(frontend_tag, 'Dockerfile.static', '--build-arg configuration="%s"' % env, base_dir=source_dir)
    push_image(frontend_tag)
    ssr_tag = 'omicsdi/omicsdi-ssr:' + img_tag
    build_image(ssr_tag, 'Dockerfile.ssr', '--build-arg configuration="%s"' % env, base_dir=source_dir)
    push_image(ssr_tag)
    k8s_service.deploy_kubernetes(env, img_tag, base_dir=source_dir)
    logger.info("Finished")


def build_generic(request_body):
    logger.info("Starting to build generic...")
    env = get_environment(request_body)
    img_tag = "omicsdi.%s.%d" % (env, request_body['pull_request']['id'])
    logger.info("Env: %s, Image tag: %s", env, img_tag)
    repo_name = request_body['repository']['name']
    img_name = "omicsdi/%s:%s" % (repo_name, img_tag)
    source_dir = os.path.join(CHECKOUT_DIR, repo_name)
    logger.info("Checking out %s:%s" % (request_body['repository']['clone_url'],
                                        request_body['pull_request']['base']['ref']))
    checkout_code(request_body['repository']['clone_url'], source_dir, request_body['pull_request']['base']['ref'])
    build_image(img_name, base_dir=source_dir)
    push_image(img_name)
    k8s_service.deploy_kubernetes(env, img_tag, base_dir=source_dir)
    logger.info("Finished")


@application.route('/github_webhooks/frontend', methods=['POST'])
def github_webhooks_frontend():
    event = request.headers.get('X-GitHub-Event', 'ping')
    if event == 'ping':
        return dumps({'msg': 'pong'})
    verify_request()
    request_body = request.get_json()
    run_async_frontend_task.delay(request_body)

    return "OK"


@application.route('/github_webhooks/generic', methods=['POST'])
def github_webhooks_generic():
    event = request.headers.get('X-GitHub-Event', 'ping')
    if event == 'ping':
        return dumps({'msg': 'pong'})
    verify_request()
    request_body = request.get_json()
    run_async_generic_task.delay(request_body)

    return "OK"


if __name__ == '__main__':
    application.run(host="0.0.0.0", port=8080, debug=True, threaded=True)
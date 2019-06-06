import os

from services import command_service


def checkout_code(repo, out_dir, branch):
    if not os.path.exists(out_dir):
        command_service.run(['git', 'clone', repo, out_dir])
    command_service.run(['cd', out_dir, '&& git checkout -f', branch, "&& git pull"])


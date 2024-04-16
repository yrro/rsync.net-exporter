# This file is used to configure gunicorn when running from the container
# image. As a result, a user can override any of these properties by providing
# additional arguments to the container.

bind = ["[::]:9770"]

accesslog = "-"

wsgi_app = "rsync_net_exporter:create_app()"

# pylint: skip-file

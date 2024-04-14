# pylint: skip-file

bind = ["[::]:9770"]

accesslog = "-"

wsgi_app = "rsync_net_exporter:create_app()"

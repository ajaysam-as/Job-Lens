web: gunicorn joblens.wsgi --log-file -
release: python manage.py compilemessages && python manage.py migrate && python manage.py collectstatic --noinput
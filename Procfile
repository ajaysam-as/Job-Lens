web: gunicorn joblens.wsgi --log-file - --timeout 120 --workers 2 --worker-class gthread --threads 4
release: python manage.py migrate && python manage.py collectstatic --noinput
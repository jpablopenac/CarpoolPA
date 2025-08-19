from app import create_app

app = create_app()

# For PythonAnywhere WSGI entrypoint
application = app

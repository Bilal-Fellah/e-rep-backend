from flask import Flask
from api import create_app

app = create_app()


@app.route('/')
def home():
    return 'Hello, World!'

@app.route('/about')
def about():
    return 'About'

if __name__ == '__main__':
    app.run(debug=True)
from api import create_app
import logging
logging.basicConfig(level=logging.INFO)


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)

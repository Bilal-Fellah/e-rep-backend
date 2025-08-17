import argparse
from api import create_app
import logging
logging.basicConfig(level=logging.INFO)


app = create_app()


from api.repositories.entity_repository import EntityRepository

# Create new entity
# entity = EntityRepository.create(name="OpenAI", type_="company")

# Fetch all entities
with app.app_context():   # <-- this sets the context
    entity = EntityRepository.delete(90)

# Update
# EntityRepository.update(entity.id, name="OpenAI Inc.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run Flask app on a specific port.')
    parser.add_argument('--port', type=int, default=5000, help='Port to run the server on')
    args = parser.parse_args()
    app.run(debug=True, port=args.port)



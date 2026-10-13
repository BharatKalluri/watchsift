from src.catalogue import service
from src.database import operations_session


def resolve(config, cards):
    with operations_session(config.database_url.get_secret_value()) as db:
        return service.resolve(config, cards, db)

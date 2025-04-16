from flask import Blueprint

# Création des blueprints pour les différentes sections de l'application
article_bp = Blueprint('article', __name__)
browse_bp = Blueprint('browse', __name__)
search_bp = Blueprint('search', __name__)
version_bp = Blueprint('version', __name__)

# Import des routes après la création des blueprints pour éviter les imports circulaires
from . import article_routes
from . import browse_routes
from . import search_routes
from . import version_routes


def register_blueprints(app):
    """
    Enregistre tous les blueprints dans l'application Flask

    Args :
        app : L'application Flask
    """
    app.register_blueprint(article_bp)
    app.register_blueprint(browse_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(version_bp)
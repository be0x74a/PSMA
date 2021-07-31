from flask import Blueprint, current_app, jsonify

blueprint = Blueprint('root', __name__)


@blueprint.route('/', methods=['GET'])
def site_map():
    routes = []
    for rule in current_app.url_map.iter_rules():
        if rule.endpoint != 'static':
            routes.append(rule.rule)

    return jsonify(code=200, endpoints=routes)
from flask import Flask, jsonify
from flask.ext.restify import Api, Resource


class User(Resource):

    def get(self):
        return jsonify({'id': 0})


app = Flask(__name__)
api = Api()
api.init_app(app)
api.add_resource(User, '/')


if __name__ == '__main__':
    app.run(debug=True)

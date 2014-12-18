from flask import Flask, jsonify
from flask.ext.restify import Api, Resource, Packable


class User(Packable):

    def __init__(self, id, email):
        self.id = id
        self.email = email

    def pack(self):
        return {
            'id': self.id,
            'email': self.email,
        }


class UserAPI(Resource):

    def get(self):
        user = User(id=1, email='demo@exmaple.com')
        return jsonify({
            'user': user
        })


app = Flask(__name__)
api = Api()
api.init_app(app)
api.add_resource(UserAPI, '/')


if __name__ == '__main__':
    app.run(debug=True)

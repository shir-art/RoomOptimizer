from flask import Flask
from flask_socketio import SocketIO

from functions.locate_furniture import Place_furniture
from db.mongo_connection import get_floor_collection, get_furniture_collection
from db.mongo_connection import get_furniture_collection

furniture = list(get_furniture_collection().find())
floor = get_floor_collection()
furniture_list = list(get_furniture_collection().find())

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")


def main():
    print("Starting server...")
    socketio.run(app, debug=True, host="0.0.0.0", port=3001)


if __name__ == '__main__':
    main()

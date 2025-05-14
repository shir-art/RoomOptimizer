#from flask import Flask
# from flask_socketio import SocketIO

from functions.locate_furniture import Place_furniture
from db.mongo_connection import get_floor_collection
from db.mongo_connection import get_furniture_collection

floor = get_floor_collection()
furniture = list(get_furniture_collection().find().limit(2))
# app = Flask(__name__)
# socketio = SocketIO(app, cors_allowed_origins="*")  # חיבור WebSocket
# import eventlet
# eventlet.monkey_patch()
#
# socketio.run(app, debug=True, host="0.0.0.0", port=3001)



def main():
    # דוגמה לקריאה לפונקציות
    # כאן תכניסי את הרשימה הממוינת של הרהיטים
    print("🔍 תוכן furniture:", furniture)
    # socketio.start_background_task(target=Place_furniture, furniture=furniture)
    # socketio.run(app, debug=True, allow_unsafe_werkzeug=True)

    Place_furniture(furniture)

if __name__ == '__main__':
    main()



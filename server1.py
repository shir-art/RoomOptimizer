import datetime
import app
from flask import Flask, request, jsonify
from db.mongo_connection import get_users_collection
from db.mongo_connection import get_requests_collection
from db.mongo_connection import get_floor_collection
from bson import ObjectId
from functions.locate_furniture import Place_furniture
from flask_cors import CORS
from classes.users import userDetails
from main import furniture, main
import traceback
from flask import request
from flask_socketio import SocketIO
from copy import deepcopy
import json

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})
socketio = SocketIO(app, cors_allowed_origins="*")
requests = get_requests_collection()

def convert_floor_to_json(floor):

    def convert(obj):
        if isinstance(obj, ObjectId):
            return str(obj)
        elif isinstance(obj, list):
            return [convert(item) for item in obj]
        elif isinstance(obj, dict):
            return {key: convert(value) for key, value in obj.items()}
        else:
            return obj

    return convert(floor)


@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get("username")
    email = data.get("email")

    if not username or not email:
        return jsonify({"success": False, "message": "החסרים פרטי משתמש או דואר אלקטרוני"}), 400

    user = get_users_collection().find_one({"name": username, "email": email})
    if user:
        userDetails.clear()
        userDetails.extend([username, email])
        return jsonify({"success": True, "message": f"משתמש מחובר: {userDetails}"}), 200
    else:
        return jsonify({"success": False, "message": "שם המשתמש או כתובת המייל שגויים😕"}), 400


@app.route('/optimize-room', methods=['POST'])
def optimize_room():
    try:
        data = request.get_json()
        furniture_ids = data.get("furnitureIds")

        if not furniture_ids or not isinstance(furniture_ids, list):
            return jsonify({"success": False, "message": "יש לשלוח רשימת מזהי רהיטים תקינה"}), 400

        # כאן אתה צריך להמיר את ה־IDs לרהיטים מלאים - תלוי איך מאוחסנים הרהיטים שלך
        # נניח שיש לך רשימה גלובלית בשם furniture עם כל הרהיטים, אז מסננים אותה כך:
        furniture_list = [furn for furn in furniture if furn["_id"] in furniture_ids]

        # תהליך סיבוב והנחה כמו שהיה קודם
        floor_collection = get_floor_collection()
        base_floor = list(floor_collection.find())
        base_floor_clean = json.loads(json.dumps(base_floor, default=str))

        combined_floor = []
        min_size_cm = get_min_furniture_unit_cm(furniture_list)
        grid_unit_cm = determine_grid_unit(min_size_cm)
        scaled_furniture = scale_furniture_to_grid(furniture_list, grid_unit_cm)

        for furn in furniture_list:
            rotated_furn = rotate_furniture(furn.copy(), furniture_list)
            floor_copy = deepcopy(base_floor_clean)
            result = Place_furniture(scaled_furniture, base_floor=floor_copy)
            combined_floor.append(result)


        floor_json = convert_floor_to_json(combined_floor)

        return jsonify({
            "success": True,
            "floor": floor_json,
            "grid_unit_cm": grid_unit_cm
        }), 200


    except Exception:
        print(traceback.format_exc())
        return jsonify({"success": False, "message": "שגיאה כללית התרחשה"}), 500

def get_min_furniture_unit_cm(furniture_list):
    min_dim = float('inf')
    for f in furniture_list:
        # כאן נוודא המרה נכונה ממטר לס"מ
        try:
            width_cm = float(f['width']) * 100  # מטרים לס"מ
            depth_cm = float(f['depth']) * 100  # מטרים לס"מ
        except Exception as e:
            print("Error converting size:", e)
            continue

        current_min = min(width_cm, depth_cm)
        if current_min < min_dim:
            min_dim = current_min

    return min_dim





def determine_grid_unit(min_cm, base_unit_cm=5):
    return max(base_unit_cm, round(min_cm / base_unit_cm) * base_unit_cm)

def scale_furniture_to_grid(furniture_list, grid_unit_cm):
    scaled = []
    for f in furniture_list:
        f = f.copy()
        f['width_grid'] = max(1, round(float(f['width']) * 100 / grid_unit_cm))
        f['depth_grid'] = max(1, round(float(f['depth']) * 100 / grid_unit_cm))
        scaled.append(f)
    return scaled

def rotate_furniture(furn, furniture_list, degrees=90):
    index = None
    for i, f in enumerate(furniture_list):
        if f == furn:
            index = i
            break
    rotated_furn = furn.copy()

    width = int(rotated_furn['width'])
    depth = int(rotated_furn['depth'])
    rotated_furn['width'] = str(depth)
    rotated_furn['depth'] = width

    if 'direction' in rotated_furn and len(rotated_furn['direction']) > 0:
        rotated_furn['direction'][0] = (rotated_furn['direction'][0] + degrees) % 360

    furniture_list[index] = rotated_furn

    return furniture_list


def run_place_furniture_parallel(furniture_items):
    for furn in furniture_items:
        rotated_furn = rotate_furniture(furn.copy())
        socketio.start_background_task(Place_furniture, furniture=[rotated_furn])


@app.route('/get-requests', methods=['GET'])
def get_requests():
    email = request.args.get("email")
    if not email:
        return jsonify({"success": False, "message": "חסר אימייל"}), 400

    requests = list(get_requests_collection().find({"user_id": email}))

    # השתמש בפונקציית ההמרה שכבר כתבת
    requests_json = convert_floor_to_json(requests)

    return jsonify({"success": True, "requests": requests_json}), 200


@app.errorhandler(404)
def not_found_error(error):
    return jsonify({"success": False, "message": "הדף לא נמצא"}), 404


@app.errorhandler(500)
def internal_error(error):
    print("שגיאת שרת:", traceback.format_exc())
    return jsonify({"success": False, "message": "שגיאת שרת. נסו שוב מאוחר יותר"}), 500


@app.errorhandler(Exception)
def unhandled_exception(e):
    print("שגיאה לא צפויה:", traceback.format_exc())
    return jsonify({"success": False, "message": "שגיאה כללית התרחשה"}), 500


@app.route('/save-room', methods=['POST'])
def save_room():
    data = request.get_json()

    if isinstance(data, list):
        # במקרה שהגיע רק furniture_list כ־list
        furniture_list = data
        floor_layout = data
    elif isinstance(data, dict):
        furniture_list = data.get("furniture_list")
        floor_layout = data
    else:
        return jsonify({"error": "Invalid request format"}), 400

    try:
        save_room_to_db(furniture_list=furniture_list, floor_layout=floor_layout)
        return jsonify({"status": "Room saved successfully"})
    except Exception as e:
        print(f"שגיאה לא צפויה: {e}")
        return jsonify({"error": str(e)}), 500



def save_room_to_db(furniture_list, floor_layout):
    room_data = {
        "user_id": userDetails ,
        "furniture_list": furniture_list,
        "floor_layout": floor_layout,
        "date": datetime.datetime.today().strftime('%Y-%m-%d %H:%M')

    }
    requests.insert_one(room_data)


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)

from flask import Flask, request, jsonify
from db.mongo_connection import get_users_collection  # חיבור למונגו
from flask_cors import CORS

# יצירת אובייקט Flask
app = Flask(__name__)

# הוספת CORS לאחר יצירת ה-Flask app
CORS(app)  # הוספת CORS לכל הכתובות

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()

    # ודא שהנתונים שמתקבלים תקינים
    username = data.get("username")
    email = data.get("email")

    if not username or not email:
        return jsonify({"success": False, "message": "החסרים פרטי משתמש או דואר אלקטרוני"}), 400

    user = get_users_collection().find_one({"name": username, "email": email})
    if user:
        return jsonify({"success": True}), 200
    else:
        return jsonify({"success": False, "message": "שם המשתמש או כתובת המייל שגויים😕"}), 400

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)

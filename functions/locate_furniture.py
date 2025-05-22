from idlelib.rpc import request_queue
from classes.floor import Floor
from db.mongo_connection import get_furniture_collection
from db.mongo_connection import get_features_collection
from db.mongo_connection import get_floor_collection
from db.mongo_connection import get_properties_collection
from db.mongo_connection import get_requests_collection
from db.mongo_connection import get_suitability_collection
from db.mongo_connection import get_users_collection

import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
import numpy as np
import matplotlib.patches as mpatches

features = get_features_collection()
floor_collection = get_floor_collection()
floor = list(floor_collection.find())
properties = get_properties_collection()
requests = get_requests_collection()
suitability = get_suitability_collection()
users = get_users_collection()
# משתנים שונים
action_stack = []  # מחסנית לשמירת הפעולות עבור רהיט שמוקם
suitability_score = None  # ציון התאמה לרהיט


def Place_furniture(furniture):
    """מקבל מערך ריהוט ממוין"""
    possible_location = []  # שמירת מיקומים אפשריים לכל רהיט
    flag = False
    for f in furniture:  # מעבר על רשימת הרהיטים
        possible_location = []
        if not check_furniture_fits_floor(f):
            continue
        possible_slots = get_possible_slots(f, possible_location)
        if not possible_slots:
            if not handle_no_possible_slots(f, furniture, possible_location):
                continue
        if not possible_location:
            print(f" {f["name"]}❌לא נמצא מקום מתאים לרהיט:  ")
            continue
        optimal = find_optimal(possible_location)
        locate(optimal, f)
        # furniture.remove(f)
        action_stack.append((f, optimal, possible_slots))
    display_floor()


def check_furniture_fits_floor(f):
    if is_furniture_for_floor(f):
        print(f"רהיט {f['_id']} מתאים לרצפה")
        return True
    else:
        print(f"שגיאה: רהיט {f['_id']} לא מתאים לרצפה")
        return False


"""בודקת אם רהיט מסוים מתאים לריצפה ( אם התכונה '2' קיימת במאפייני הרהיט)"""


def is_furniture_for_floor(furniture_item):
    return 2 in furniture_item['features']


"מחזירה רשימת משבצות שמתאימות לרהיט על פי התאמת מאפיינים"


def get_possible_slots(f, possible_location):
    possible_slots = []
    for i, slot in enumerate(floor):
        x = Location_matching_check(f['features'], slot, f, possible_location)
        if x not in [True, False]:
            i = next((index for index, s in floor if s["properties"].get("X") == x), i)
        if x == True:
            possible_slots.append(slot)
    return possible_slots


"מטפלת במקרה שבו לא נמצאו משבצות מתאימות לרהיט"


def handle_no_possible_slots(f, furniture, possible_location):
    cancel_action(f, furniture)
    if not possible_location:
        is_possible = check_last()
        if not is_possible:
            display_floor()
            raise ValueError("לא נמצאה התאמה לחדר זה")
        return True
    else:
        prev_furniture, prev_slot, prev_possible_slots = possible_location.pop()
        remove_furniture(prev_furniture, prev_slot, f, furniture)
        if prev_possible_slots:
            possible_location.append((prev_furniture, prev_slot, prev_possible_slots))
            furniture.insert(0, prev_furniture)
        return False


def Location_matching_check(furniture_features, start_slot, furniture, possible_location):
    # קריאה לפונקציה לבדוק אם המשבצת מתאימה
    if not is_slot_suitable(furniture_features, start_slot["properties"]):
        return False  # אם המשבצת לא מתאימה, נחזיר False

    # קריאה לפונקציה check_neighbors כדי לבדוק את השכנים
    x = check_neighbors(start_slot, furniture, possible_location)
    if not x:
        return False  # אם השכנים לא מתאימים, נחזיר False
    # else:
    # print(f"🩷נמצאה התאמה לשכנים: {x}")

    # חישוב ציון התאמה על סמך ההתאמות

    return x  # אם הכל תקין, נחזיר את ציון ההתאמה


def is_slot_suitable(furniture_features, slot_properties):
    slot_prop_ids = []
    for prop in slot_properties:
        try:
            slot_prop_ids.append(prop["_id"])
            # print(f"התכונה של המשבצת  {slot_prop_ids}")
        except KeyError as e:
            print(f"שגיאת מפתח: {e}")
            continue
    flag = False

    for feature in furniture_features:
        required_id = feature
        if required_id != "1":
            flag = False
        if required_id in slot_prop_ids:
            flag = True

            # להוסיף עצירה

        # print("✅ נמצאה התאמה לכל התכונות")
        return flag


def check_neighbors(slot, furniture, possible_location):
    """
    בודקת אם כל השכנים במימדים של הרהיט, כולל גובה, מתאימים למיקום
    """
    if is_too_close_to_existing_furniture(slot, furniture):
        return False
    if not is_within_floor_bounds(slot, furniture):
        return False
    if has_invalid_neighbors(slot, furniture):
        return False
    if has_invalid_property_32(slot, furniture):
        return False

    suitability_score = furniture["suitability_id"]
    possible_location.append((furniture, slot, suitability_score))
    return True


"בודק האם הרהיט קרוב מדי לרהיטים קיימים (פחות ממרחק מינימלי)"


def is_too_close_to_existing_furniture(slot, furniture):
    MIN_DISTANCE = 2
    new_x1 = slot["x"]
    new_y1 = slot["y"]
    new_x2 = new_x1 + int(furniture["width"]) - 1
    new_y2 = new_y1 + int(furniture["depth"]) - 1

    for placed_furniture, placed_slot, _ in action_stack:
        placed_x1 = placed_slot["x"] - MIN_DISTANCE
        placed_y1 = placed_slot["y"] - MIN_DISTANCE
        placed_x2 = placed_slot["x"] + int(placed_furniture["width"]) + MIN_DISTANCE - 1
        placed_y2 = placed_slot["y"] + int(placed_furniture["depth"]) + MIN_DISTANCE - 1

        if not (new_x2 < placed_x1 or new_x1 > placed_x2 or new_y2 < placed_y1 or new_y1 > placed_y2):
            return True
    return False


"בודק שהרהיט לא חורג מהגבולות של המטריצה בכל שלושת הצירים"


def is_within_floor_bounds(slot, furniture):
    min_x = min(s["x"] for s in floor)
    max_x = max(s["x"] for s in floor)
    min_y = min(s["y"] for s in floor)
    max_y = max(s["y"] for s in floor)
    min_z = min(s["z"] for s in floor)
    max_z = max(s["z"] for s in floor)

    for dx in range(int(furniture["width"])):
        for dy in range(int(furniture["depth"])):
            for dz in range(int(furniture["high"])):
                if not (min_x <= slot["x"] + dx <= max_x and
                        min_y <= slot["y"] + dy <= max_y and
                        min_z <= slot["z"] + dz <= max_z):
                    return False
    return True


" בודק האם יש שכנים פסולים (קיר, דלת, חלון) מסביב לרהיט"


def has_invalid_neighbors(slot, furniture):
    for dx in range(int(furniture["width"])):
        for dy in range(int(furniture["depth"])):
            x = slot["x"] + dx
            y = slot["y"] + dy
            z = slot["z"]

            neighbor_slot = next((s for s in floor if s["x"] == x and s["y"] == y and s["z"] == z), None)
            if neighbor_slot is None:
                return True

            for prop in neighbor_slot.get("properties", []):
                if isinstance(prop, dict) and prop.get("value") == "wall":
                    return True

            for offset_x in range(-3, 3):
                for offset_y in range(-3, 3):
                    door_slot = next((s for s in floor if s["x"] == x + offset_x and s["y"] == y + offset_y and s["z"] == z), None)
                    if door_slot:
                        for prop in door_slot.get("properties", []):
                            if isinstance(prop, dict) and str(prop.get("value", "")).strip().lower() == "door":
                                return True

            for offset_x in range(-3, 4):
                for offset_y in range(-3, 4):
                    window_slot = next((s for s in floor if s["x"] == x + offset_x and s["y"] == y + offset_y and s["z"] == z), None)
                    if window_slot:
                        for prop in window_slot.get("properties", []):
                            if isinstance(prop, dict) and str(prop.get("value", "")).strip().lower() == "window":
                                return True
    return False


"בודק האם הערך של התכונה 32 קטן מגובה הרהיט או שהתכונות לא מתאימות"


def has_invalid_property_32(slot, furniture):
    property_32_value = next(
        (prop["32"] for prop in slot["properties"] if isinstance(prop, dict) and "32" in prop), None)

    if property_32_value is not None:
        if not int(furniture["high"]) <= property_32_value:
            return True
        if not is_slot_suitable(furniture["features"], slot["properties"]):
            return True
    return False


"ביטול הפעולה האחרונה"
def cancel_action(furniture_item, furniture):
    if not action_stack:
        return
    prev_furniture, prev_slot, prev_possible_slots = action_stack.pop()
    remove_furniture(prev_furniture, prev_slot, furniture_item, furniture)

    if prev_possible_slots:
        action_stack.append((prev_furniture, prev_slot, prev_possible_slots))
    # sorted_furniture_list.insert(0, prev_furniture)
    else:
        return


"מסירה רהיט מהמשבצת שבה היה מונח ומחזירה את המשבצת למצב 'פנוי'"
def remove_furniture(prev_furniture, prev_slot, furniture_item, furniture):
    # חישוב הגבולות של הרהיט
    x_end = prev_slot["x"] + int(prev_furniture["width"])
    y_end = prev_slot["y"] + int(prev_furniture["depth"])
    z_end = prev_slot["z"] + int(prev_furniture["high"])

    # עבור כל המיקומים של הרהיט, עדכן את המשבצות בהתאם
    clear_furniture_area(prev_slot, {
        "width": int(prev_furniture["width"]),
        "depth": int(prev_furniture["depth"]),
        "high": int(prev_furniture["high"])
    })

    # הסרת הרהיט מתוך רשימת הרהיטים
    sorted_furniture_list = [f for f in furniture if
                             not (isinstance(f, dict) and f["_id"] == prev_furniture["_id"])]
    # return sorted_furniture_list
# להוסיף בדיקה מעמיקה


def clear_furniture_area(start_slot, dimensions):
    x_end = start_slot["x"] + dimensions["width"]
    y_end = start_slot["y"] + dimensions["depth"]
    z_end = start_slot["z"] + dimensions["high"]

    for x in range(start_slot["x"], x_end):
        for y in range(start_slot["y"], y_end):
            for z in range(start_slot["z"], z_end):
                slot = next((s for s in floor if s["x"] == x and s["y"] == y and s["z"] == z), None)
                if slot:
                    slot["properties"] = [{"_id": 1, "value": "empty"}]


def find_optimal(possible_location):
    """מחזיר את המשבצת עם הציון הגבוה ביותר"""
    if not possible_location:
        return None

    try:
        # מציאת האיבר עם הציון הגבוה ביותר
        best_entry = max(possible_location, key=lambda entry: entry[2])  # 🔍 מחפש את הערך הגדול ביותר בציון

        location_data = best_entry[1]  # ✅ קבלת המשבצת המתאימה

        if not isinstance(location_data, dict):  # ודא שהוא מילון
            raise TypeError("המיקום אינו מילון!")

        return location_data  # ✅ מחזירים את המשבצת עם הציון הגבוה ביותר

    except Exception as e:
        print(f"❌ שגיאה: {type(e).__name__} - {e}")  # ✅ הדפסת סוג השגיאה
        return None  # טיפול בבעיה


" ממקמת את הרהיט על פני האזור שבו הוא אמור להיות"
def locate(optimal_slot, furniture):
    start_x, start_y, start_z = optimal_slot["x"], optimal_slot["y"], optimal_slot["z"]
    width = int(furniture["width"])
    depth = int(furniture["depth"])
    height = int(furniture["high"])
    f_type = furniture["type"].lower().strip()

    new_property = {
        "_id": 31,
        "value": "furniture",
        "furniture": f_type
    }
    for x in range(start_x, start_x + width):
        for y in range(start_y, start_y + depth):
            # for z in range(start_z, start_z + height):
            slot = next((s for s in floor if s["x"] == x and s["y"] == y), None)

            if slot:
                update_slot_with_furniture(slot, furniture)


def update_slot_with_furniture(slot, furniture):
    slot["properties"] = [{"_id": 2, "value": "occupied"}]
    slot["properties"].append({
        "_id": 31,
        "value": "furniture",
        "furniture": furniture["_id"]
    })


def check_last():  # בדיקה האם קיים פתרון על ידי בדיקת האיבר הראשון במחסנית
    return bool(action_stack)


def Fitness_Score():
    return


def elimination():
    return


def print_room_state():
    for item in floor:
        print("_id:", item["_id"])
        print("x:", item["x"])
        print("y:", item["y"])
        print("z:", item["z"])
        print("properties:")
        for i, prop in enumerate(item.get("properties", [])):
            print(f"  {i}:")
            # print(f"    _id: {prop['_id']}")
            print(f"    value: {prop['value']}")
        print()
    print("finish🛼")


def display_floor():
    max_x = max(slot['x'] for slot in floor) + 1
    max_y = max(slot['y'] for slot in floor) + 1

    grid = np.zeros((max_y, max_x), dtype=int)

    # מפה של ערכים לקוד צבע
    value_to_color = {
        'wall': 1,
        'empty': 2,
        'null': 3,
        'wardrobe3': 4,
        'wardrobe4': 5,
        'wardrobe5': 6,
        'wardrobe6': 7,
        'door': 8,
        'window': 9

    }
    # הגדרת צבעים תואמים למספרים
    colors = ['black', 'white', 'white', 'coral', 'cyan', 'crimson', 'orchid', 'gray', 'blue']
    legend_labels = ['Wall', 'Empty', 'null', 'wardrobe3', 'wardrobe4', 'wardrobe5', 'wardrobe6', 'Door', 'Window']

    for slot in floor:
        x, y = slot['x'], slot['y']
        props = slot.get('properties', [])

        furniture_type = None
        for p in props:
            if isinstance(p, dict) and p.get('value', '') == 'furniture':
                furniture_type = str(p.get('furniture', '')).lower().strip()

        cell_value = 0

        if furniture_type:
            # אם הסוג כבר במפה – השתמשי בו. אחרת תוסיפי אותו עם מספר חדש
            if furniture_type not in value_to_color:
                value_to_color[furniture_type] = len(value_to_color) + 1
                colors.append(np.random.choice([
                    'yellow', 'purple', 'brown', 'pink', 'cyan', 'olive', 'teal'
                ]))  # צבעים רנדומליים לסוגים חדשים
                legend_labels.append(furniture_type.capitalize())

            cell_value = value_to_color[furniture_type]

        else:
            for key, val in value_to_color.items():
                if key in [str(p.get('value', '')).strip().lower() for p in props]:
                    cell_value = val
                    break

        grid[y][x] = cell_value
    cmap = ListedColormap(colors)

    # ציור
    plt.figure(figsize=(15, 15))
    plt.imshow(grid, cmap=cmap, origin='lower')
    plt.title("Room layout")
    plt.xticks(range(max_x))
    plt.yticks(range(max_y))
    plt.grid(True, color='gray', linewidth=0.5)

    patches = [mpatches.Patch(color=colors[i], label=legend_labels[i]) for i in range(len(colors))]
    plt.legend(handles=patches, bbox_to_anchor=(1.05, 1), loc='upper left')

    plt.tight_layout()
    plt.show()

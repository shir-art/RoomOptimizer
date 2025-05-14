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

#furniture = list(get_furniture_collection().find().limit(1))

print("📦 נטען אוסף רהיטים מה־DB:")
# for furniture in furniture:
# print(f"  רהיט ID: {furniture.get('_id')}, מאפיינים: {furniture.get('features')}")
features = get_features_collection()
floor_collection = get_floor_collection()
floor = list(floor_collection.find())
properties = get_properties_collection()
requests = get_requests_collection()
suitability = get_suitability_collection()
users = get_users_collection()
# משתנים שונים
action_stack = []  # מחסנית לשמירת הפעולות עבור רהיט שמוקם
possible_location = []  # שמירת מיקומים אפשריים לכל רהיט
suitability_score = None  # ציון התאמה לרהיט
#from flask import Flask

#app = Flask(__name__)

# import eventlet
# eventlet.monkey_patch()


def Place_furniture(furniture):
    """מקבל מערך ריהוט ממוין"""

    flag = False
    for f in furniture:  # מעבר על רשימת הרהיטים
        # print(f"תכונות הרהיט: {f}")  # הדפס את כל המידע על הרהיט
        # if 'f' in furniture:
        possible_location = []
        # print(f" תכונות: {f['features']}")  # הדפס את התכונות אם קיימות
        if 2 in f['features']:  # אם הרהיט מונח על הרצפה
            print('😍🩷😘😊הרהיט ממוקם ברצפה')
            possible_slots = []  # רשימת המקומות האפשריים
            #for slot in floor:  # מעבר על כל המשבצות
            for i, slot in enumerate(floor):
                x = Location_matching_check(f['features'],slot, f)
                if x != True and x != False:
                    i = next((index for index, s in floor if s["properties"].get("X") == x), i)                # print(f"בדיקת משבצת x:{slot['x']} y:{slot['y']} → properties: {slot['properties']}")
                # print(f"בהשוואה ל: {f['features']}")
                if x == True:
                    possible_slots.append(slot)  # שמירה של כל המקומות האפשריים
            if not possible_slots:  # אם אין מקומות אפשריים
                cancel_action(f)
                if not possible_location:
                    is_possible = check_last()
                    if not is_possible:
                        raise ValueError("לא נמצאה התאמה לחדר זה")

                prev_furniture, prev_slot, prev_possible_slots = possible_location.pop()
                remove_furniture(prev_furniture, prev_slot, f, furniture)

                if prev_possible_slots:
                    possible_location.append((prev_furniture, prev_slot, prev_possible_slots))
                    furniture.insert(0, prev_furniture)
                else:
                    continue

            optimal = find_optimal(possible_location)
            locate(optimal, f)
            action_stack.append((f, optimal, possible_slots))

    # Improvement_with_genetic_algorithm(floor)
    display_floor()
    #print_room_state()


def Improvement_with_genetic_algorithm(rooms):
    # for room in rooms:
    # Fitness_Score(room) #שליחה לפונקציה שמשפרת את התוצאה בעזרת אלגוריתם גנטי
    Next_generation_room_candidates = elimination(rooms)


def Location_matching_check(furniture_features,start_slot, furniture):
    # קריאה לפונקציה לבדוק אם המשבצת מתאימה
    if not is_slot_suitable(furniture_features, start_slot["properties"]):
        return False  # אם המשבצת לא מתאימה, נחזיר False

    # קריאה לפונקציה check_neighbors כדי לבדוק את השכנים
    x = check_neighbors(start_slot, furniture)
    if not x:
        return False  # אם השכנים לא מתאימים, נחזיר False
    # else:
        #print(f"🩷נמצאה התאמה לשכנים: {x}")

    # חישוב ציון התאמה על סמך ההתאמות

    return x  # אם הכל תקין, נחזיר את ציון ההתאמה


def is_slot_suitable(furniture_features, slot_properties):
    slot_prop_ids = []
    for prop in slot_properties:
        try:
            slot_prop_ids.append(prop["_id"])
            #print(f"התכונה של המשבצת  {slot_prop_ids}")
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


def check_neighbors(slot, furniture):
    """
    בודקת אם כל השכנים במימדים של הרהיט, כולל גובה, מתאימים למיקום
    """
    furniture_width = int(furniture["width"])
    furniture_depth = int(furniture["depth"])
    furniture_height = int(furniture["high"])
    start_x = slot["x"]
    start_y = slot["y"]
    start_z = slot["z"]

    # חיפוש אחרי הגבולות של המטריצה מתוך כל התאים
    min_x = min(s["x"] for s in floor)
    max_x = max(s["x"] for s in floor)
    min_y = min(s["y"] for s in floor)
    max_y = max(s["y"] for s in floor)
    min_z = min(s["z"] for s in floor)
    max_z = max(s["z"] for s in floor)

    # בדיקת גבולות לפני בדיקת השכנים
    if not all(
            min_x <= start_x + dx <= max_x and
            min_y <= start_y + dy <= max_y and
            min_z <= start_z + dz <= max_z
            for dx in range(furniture_width)
            for dy in range(furniture_depth)
            for dz in range(furniture_height)
    ):
        return False

    for dx in range(int(furniture_width)):
        for dy in range(int(furniture_depth)):
            #for dz in range(int(furniture_height)):
            #neighbor_x = start_x + dx
            #neighbor_y = start_y + dy
                # neighbor_z = start_z + dz

            # חיפוש הערך של "32" בתוך `properties`
            property_32_value = next(
                (prop["32"] for prop in slot["properties"] if isinstance(prop, dict) and "32" in prop), None)

            # שימוש בערך שנמצא
            if property_32_value is not None and not furniture_height <= property_32_value and is_slot_suitable(
                    furniture["features"], slot["properties"]):
                return dx

            # neighbor_slot = None
               # for s in floor:
                #    if s["x"] == neighbor_x and s["y"] == neighbor_y and s["z"] == neighbor_z:
                #        neighbor_slot = s
                 #       break

               # if neighbor_slot is None:
                #    print(f"שכן לא נמצא: {neighbor_x=}, {neighbor_y=}, {neighbor_z=}")
                #    return False

                #if not is_slot_suitable(furniture["features"], neighbor_slot["properties"]):
                  #  return False

                # if not Location_matching_check(furniture["features"], neighbor_slot["properties"], slot, furniture):
                #     return False
    suitability_score = furniture["suitability_id"]
    possible_location.append((furniture, slot, suitability_score))
    return True


# def is_slot_suitable(slot):
# כאן תוכל לבדוק אם המשבצת מתאימה לדרישות שלך
# לדוגמה, אם היא ריקה או אם תכונה אחרת מתאימה
# return slot.get("is_empty", False)  # אם המשבצת ריקה (בהנחה שיש תכונה כזו)


# def is_slot_suitable(slot):
# כאן לבדוק אם המשבצת מתאימה לדרישות

# return

def cancel_action(furniture_item):
    """ביטול הפעולה האחרונה"""
    if not action_stack:
        return
    prev_furniture, prev_slot, prev_possible_slots = action_stack.pop()
    remove_furniture(prev_furniture, prev_slot, furniture_item)

    if prev_possible_slots:
        action_stack.append((prev_furniture, prev_slot, prev_possible_slots))
       # sorted_furniture_list.insert(0, prev_furniture)
    else:
        return


def remove_furniture(prev_furniture, prev_slot, furniture_item, furniture):
    """
    מסירה רהיט מהמשבצת שבה היה מונח ומחזירה את המשבצת למצב 'פנוי'
    """
    # חישוב הגבולות של הרהיט
    x_end = prev_slot["x"] + int(prev_furniture["width"])
    y_end = prev_slot["y"] + int(prev_furniture["depth"])
    z_end = prev_slot["z"] + int(prev_furniture["high"])

    # עבור כל המיקומים של הרהיט, עדכן את המשבצות בהתאם
    for x in range(prev_slot["x"], x_end):
        for y in range(prev_slot["y"], y_end):
            for z in range(prev_slot["z"], z_end):
                # עדכון המשבצת הרלוונטית למצב 'פנוי'
                slot = next((s for s in floor if s["x"] == x and s["y"] == y and s["z"] == z), None)
                if slot:
                    slot["properties"] = [{"_id": 1, "value": "empty"}]
    # הסרת הרהיט מתוך רשימת הרהיטים
    sorted_furniture_list = [f for f in furniture if
                 not (isinstance(f, dict) and f["_id"] == prev_furniture["_id"])]

    #return sorted_furniture_list


# להוסיף בדיקה מעמיקה
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


def locate(optimal_slot, furniture):
    """
    ממקמת את הרהיט על פני האזור שבו הוא אמור להיות.
    """
    start_x, start_y, start_z = optimal_slot["x"], optimal_slot["y"], optimal_slot["z"]

    width = int(furniture["width"])
    depth = int(furniture["depth"])
    height = int(furniture["high"])
    new_property = {
        "_id": 31,
        "value": "furniture",
        "furniture": ""
    }
    for x in range(start_x, start_x + width):
        for y in range(start_y, start_y + depth):
            #for z in range(start_z, start_z + height):
            if(x==1 and y ==1):
                print("vvvvvvvvvvvvvvv")
            slot = next((s for s in floor if s["x"] == x and s["y"] == y ), None)

            if slot:
                slot["properties"] = [{"_id": 2, "value": "occupied"}]

                # הוספת האובייקט החדש לרשימת properties
                slot["properties"].append(new_property)

                # עכשיו ניתן לעדכן את שם הרהיט אחרי שהמאפיין "furniture" כבר קיים
                slot["properties"][-1]["furniture"] = furniture["_id"]



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
            #print(f"    _id: {prop['_id']}")
            print(f"    value: {prop['value']}")
        print()  # רווח בין האובייקטים
    print("finish🛼")




def display_floor():
    max_x = max(slot['x'] for slot in floor) + 1
    max_y = max(slot['y'] for slot in floor) + 1

    grid = np.zeros((max_y, max_x), dtype=int)

    # מפה של ערכים לקוד צבע
    value_to_color = {
        'wall': 1,
        'empty': 2,
        'fff': 3,
        'occupied': 4,
        'furniture': 5
    }

    for slot in floor:
        x, y = slot['x'], slot['y']
        props = [str(p.get('value', '')).strip().lower() for p in slot.get('properties', [])]
        print(f"x: {x}, y: {y}, props: {props}")

        found = False
        for key, val in value_to_color.items():
            if key in props:
                grid[y][x] = val
                found = True
                break
        if not found:
            grid[y][x] = 0  # ברירת מחדל – ריק לגמרי
    print(np.unique(grid, return_counts=True))

    # הגדרת צבעים תואמים למספרים
    colors = ['white', 'black', 'lightgray', 'green', 'orange', 'blue']  # 0-5
    cmap = ListedColormap(colors)

    # ציור
    plt.figure(figsize=(15, 15))
    plt.imshow(grid, cmap=cmap, origin='lower')
    plt.title("Room layout")
    plt.xticks(range(max_x))
    plt.yticks(range(max_y))
    plt.grid(True, color='gray', linewidth=0.5)

    legend_labels = ['None', 'Wall', 'Empty', 'FFF', 'Occupied', 'Furniture']
    patches = [mpatches.Patch(color=colors[i], label=legend_labels[i]) for i in range(len(colors))]
    plt.legend(handles=patches, bbox_to_anchor=(1.05, 1), loc='upper left')

    plt.tight_layout()
    plt.show()


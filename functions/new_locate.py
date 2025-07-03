from datetime import datetime
from db.mongo_connection import get_features_collection
from db.mongo_connection import get_floor_collection
from db.mongo_connection import get_properties_collection
from db.mongo_connection import get_requests_collection
from db.mongo_connection import get_suitability_collection
from db.mongo_connection import get_users_collection
from classes.users import userDetails
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches


features = get_features_collection() #רשימת תכונות אפשריות לרהיטים
properties = get_properties_collection()#רשימת תכונות אפשריות למשבצת ברצפה
requests = get_requests_collection()#קולקציית בקשות קודמות של משתמש
suitability = get_suitability_collection()#מידות התאמה בין מיקום לרהיט
"משתנים שונים"
action_stack = []  # מחסנית לשמירת הפעולות עבור רהיט שמוקם
suitability_score = None  # ציון התאמה לרהיט


def Place_furniture(furniture, base_floor):
    """פונקציה ראשית למיקום רהיטים - בודקת האם משבצת מתאימה לרהיט"""
    for f in furniture:#לולאה שעוברת על כל הרהיטים
        possible_location = []#רשימת מקומות אפשריים לרהיט נוכחי
        if not check_furniture_fits_floor(f):
            continue#TODO - להוסיף פונקציה לרהיט תלוי
        possible_slots = get_possible_slots(f, possible_location, base_floor)#משבצות אפשריות למיקום
        if not possible_slots:
            #TODO מפה לעבור שוב מבחינת הגיון והבנה
            if not handle_no_possible_slots(f, furniture, possible_location, base_floor):
                continue
        if not possible_location:
            continue
        optimal = find_optimal(possible_location)
        locate(optimal, f, base_floor)
        action_stack.append((f, optimal))

    return base_floor


def check_furniture_fits_floor(f):
    """בדיקה האם רהיט מונח על הרצפה"""
    if is_furniture_for_floor(f):
        return True
    else:
        return False


def is_furniture_for_floor(furniture_item):
    """"בדיקה אם רהיט מתאים לריצפה """
    return 2 in furniture_item['features']


#*****
def get_possible_slots(f, possible_location, floor):
    """מחזירה רשימת משבצות שמתאימות לרהיט על פי התאמת מאפיינים"""
    possible_slots = []
    for i, slot in enumerate(floor):
        x = Location_matching_check(f['features'], slot, f, possible_location, floor)
        if x not in [True, False]:
            i = next((j for j, s in enumerate(floor) if s["properties"].get("X") == x), i)
            slot = floor[i]  # מעדכנים את המשבצת לחדשה לפי ה־X שנמצא
        if x is True:
            possible_slots.append(slot)
    return possible_slots


def Location_matching_check(furniture_features, start_slot, furniture, possible_location, floor):
    """בדיקת התאמה למיקום"""
    # קריאה לפונקציה לבדוק אם המשבצת מתאימה
    if not is_slot_suitable(furniture_features, start_slot["properties"]):
        return False

    all_features = list(features.find())
    furniture_feature_ids = furniture.get("features", [])
    furniture_features = [f for f in all_features if f["_id"] in furniture_feature_ids]
    # קריאה לפונקציה check_neighbors כדי לבדוק את השכנים
    x = check_neighbors(start_slot, furniture, possible_location, floor, furniture_features)

    if not x:
        return False
    #TODO חישוב ציון התאמה על סמך ההתאמות
    return x


#*****
def is_slot_suitable(furniture_features, slot_properties):
    """"בדיקת התאמת משבצת"""
    slot_prop_ids = [prop["_id"] for prop in slot_properties]
    if 1 not in slot_prop_ids:#במקרה שהמשבצת NULL או שהיא אינה ריקה
        return False
    #TODO לבדוק תכונות משבצת מול רהיט
    #for required_id in furniture_features:
        #if required_id not in slot_prop_ids:
            #return False
    return True

#*****
def check_neighbors(slot, furniture, possible_location, floor, furniture_features):
    """בדיקת שכנים של משבצת-בודקת אם כל השכנים במימדים של הרהיט, כולל גובה, מתאימים למיקום"""
    if is_too_close_to_existing_furniture(slot, furniture, furniture_features):
        return False
    if not check_wall_fit(slot, furniture, floor):
        return False
    if not is_within_floor_bounds(slot, furniture, floor):
        return False
    if has_invalid_neighbors(slot, furniture, floor):
        return False
    suitability_score = calculate_suitability_score(slot, furniture, floor)
    possible_location.append((furniture, slot, suitability_score))
    return True


def is_too_close_to_existing_furniture(slot, furniture, furniture_features):
    """בדיקה האם הרהיט קרוב מדי לרהיטים קיימים (פחות ממרחק מינימלי)"""
    if len(action_stack) == 0:
        return False
    side_type = get_furniture_side_type(furniture)
    min_distance = get_furniture_distance_by_side(side_type, furniture_features)
    return is_too_close_to_elements(slot, furniture, action_stack, min_distance, element_type="furniture")


def get_furniture_side_type(furniture):
    width = int(furniture["width"])
    depth = int(furniture["depth"])
    return "wide" if width >= depth else "narrow"


def get_furniture_distance_by_side(side_type, features_collection):
    search_value = f"distance from furniture on the {side_type} side"
    for feature in features_collection:
        if feature.get("value", "").lower() == search_value:
            return feature.get("distance", 1)
    return 1  # ברירת מחדל אם לא נמצא


#TODO הבנה  מלא של הקוד
#****
def check_wall_fit(slot, furniture, floor):
    """ בדיקת יחסיות נכונה בין הרהיט לקיר לפי תכונות הרהיט"""
    features_list = list(features.find())
    feature_dict = {f["_id"]: f for f in features_list}
    # יצירת רשימת תכונות מלאה לרהיט – לפי מזהי התכונות שמופיעים בו
    features_full = [
        feature_dict[feature_id]
        for feature_id in furniture.get("features", [])
        if feature_id in feature_dict
    ]
    # יצירת מיפוי בין מזהה התכונה לערך שלה
    feature_map = {f["_id"]: f["value"].lower() for f in features_full}
    #בדיקה של רהיט שהצד הרחב בו אמור להיות צמוד לקיר
    if 15 in feature_map:
        return check_adjacent_to_wall_by_side(slot, furniture, floor, "wide")
    #בדיקה עבור רהיט שהצד הצר בו אמור להיות צמוד לקיר
    if 18 in feature_map:
        return check_adjacent_to_wall_by_side(slot, furniture, floor, "narrow")
    #רהיט במרכז החדר
    if 14 in feature_map:
        return not check_adjacent_to_wall(slot, furniture, floor)
    #רהיט בפינה
    if 19 in feature_map:
        return check_in_corner(slot, furniture, floor)

    return True


def check_adjacent_to_wall_by_side(slot, furniture, floor, side_type):
    """בדיקה האם הצד הרחב של הרהיט הוא הצמוד לקיר"""
    x0, y0 = slot["x"], slot["y"]
    width = int(furniture["width_grid"])
    depth = int(furniture["depth_grid"])
    is_wide_along_x = width >= depth
    side = "x" if (side_type == "wide" and is_wide_along_x) or (side_type == "narrow" and not is_wide_along_x) else "y"

    wall_tiles = [
        s for s in floor
        if any(p.get("value", "").lower() == "wall" for p in s.get("properties", []))
    ]

    edge_tiles = []
    if side == "x":
        for dy in range(depth):
            for dx in [0, width - 1]:
                edge_tiles.append({"x": x0 + dx, "y": y0 + dy})
    else:
        for dx in range(width):
            for dy in [0, depth - 1]:
                edge_tiles.append({"x": x0 + dx, "y": y0 + dy})

    return is_too_close_to_elements(slot, furniture, edge_tiles, 1, element_type="wall")


def has_wall_along_x_edge(x0, y0, width, depth, floor):
    """בודקת קיר על ציר הX"""
    for dy in range(depth):
        for dx in [0, width - 1]:
            x = x0 + dx
            y = y0 + dy
            if is_wall_adjacent(x, y, floor):
                return True
    return False

def has_wall_along_y_edge(x0, y0, width, depth, floor):
    """בודקת קיר על ציר Y"""
    for dx in range(width):
        for dy in [0, depth - 1]:
            x = x0 + dx
            y = y0 + dy
            if is_wall_adjacent(x, y, floor):
                return True
    return False


def is_wall_adjacent(x, y, floor):
    """בודקת אם יש קיר סמוך למשבצת"""
    for nx, ny in [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]:
        for s in floor:
            if s["x"] == nx and s["y"] == ny:
                for prop in s.get("properties", []):
                    if prop.get("value", "").lower() == "wall":
                        return True
    return False


def check_adjacent_to_wall(slot, furniture, floor):
    """בדיקה אם יש קיר ליד הרהיט"""
    wall_tiles = [
        s for s in floor
        if any(p.get("value", "").lower() == "wall" for p in s.get("properties", []))
    ]
    return is_too_close_to_elements(slot, furniture, wall_tiles, 1, element_type="wall")



def check_in_corner(slot, furniture, floor):
    """בדיקה אם הרהיט בפינה"""
    x0, y0 = slot["x"], slot["y"]
    width = int(furniture["width_grid"])
    depth = int(furniture["depth_grid"])

    corners = [
        (x0, y0),  # פינה שמאלית עליונה
        (x0 + width - 1, y0),  # פינה ימנית עליונה
        (x0, y0 + depth - 1),  # פינה שמאלית תחתונה
        (x0 + width - 1, y0 + depth - 1)  # פינה ימנית תחתונה
    ]

    wall_touch_count = 0
    for x, y in corners:
        if is_wall_adjacent(x, y, floor):
            wall_touch_count += 1
    # רהיט נחשב בפינה אם לפחות שתי פינות צמודות לקיר
    return wall_touch_count >= 2


def is_too_close_to_elements(slot, furniture, elements, min_distance, element_type="furniture"):
    """בדיקה כללית אם רהיט קרוב מדי לרשימת אלמנטים - רהיטים או קירות"""
    new_x1 = slot["x"]
    new_y1 = slot["y"]
    new_x2 = new_x1 + int(furniture["width_grid"]) - 1
    new_y2 = new_y1 + int(furniture["depth_grid"]) - 1

    for element in elements:
        if element_type == "furniture":
            existing_furniture, existing_slot = element
            ex_x1 = existing_slot["x"] - min_distance
            ex_y1 = existing_slot["y"] - min_distance
            ex_x2 = existing_slot["x"] + int(existing_furniture["width_grid"]) + min_distance - 1
            ex_y2 = existing_slot["y"] + int(existing_furniture["depth_grid"]) + min_distance - 1

        elif element_type == "wall":
            x = element["x"]
            y = element["y"]
            ex_x1 = x - min_distance
            ex_y1 = y - min_distance
            ex_x2 = x + min_distance
            ex_y2 = y + min_distance

        else:
            continue

        if not (new_x2 < ex_x1 or new_x1 > ex_x2 or new_y2 < ex_y1 or new_y1 > ex_y2):
            return True

    return False


def is_within_floor_bounds(slot, furniture, floor):
    """בדיקה שהרהיט לא חורג מהגבולות של החדר בכל שלושת הצירים"""
    #מציאת גבולות החדר
    min_x = min(s["x"] for s in floor)
    max_x = max(s["x"] for s in floor)
    min_y = min(s["y"] for s in floor)
    max_y = max(s["y"] for s in floor)
    min_z = min(s["z"] for s in floor)
    max_z = max(s["z"] for s in floor)
    #מעבר על גבולות הרהיט ובדיקת חריגה
    for dx in range(int(furniture["width_grid"])):
        for dy in range(int(furniture["depth_grid"])):
            for dz in range(int(furniture["high"])):
                if not (min_x <= slot["x"] + dx <= max_x and
                        min_y <= slot["y"] + dy <= max_y and
                        min_z <= slot["z"] + dz <= max_z):
                    return False
    return True

#*****
def has_invalid_neighbors(slot, furniture, floor):
    """בודקת אם רהיט חוסם משהו"""
    if blocks_wall_or_socket(slot, furniture, floor):
        return True
    if blocks_element_nearby(slot, furniture, floor, element="door", radius=2, check_z=False):
        return True
    if blocks_element_nearby(slot, furniture, floor, element="window", radius=3, check_z=True):#בבדיקת חלון נבדק רדיוס גדול יותר כדי לא לחסום זרימת אוויר
        return True
    return False


def blocks_wall_or_socket(slot, furniture, floor):
    """בודקת אם רהיט חוסם קיר או שקע"""
    fw = int(furniture["width_grid"])
    fd = int(furniture["depth_grid"])
    fz = slot["z"]
    fh = int(furniture.get("high", 1))

    for dx in range(fw):
        for dy in range(fd):
            x = slot["x"] + dx
            y = slot["y"] + dy
            for s in floor:
                if s["x"] == x and s["y"] == y:
                    for prop in s.get("properties", []):
                        val = str(prop.get("value", "")).strip().lower()
                        if val == "wall":
                            return True
                        if val == "socket":
                            if fz + fh > s["z"]:
                                return True
    return False


def blocks_element_nearby(slot, furniture, floor, element, radius, check_z=False):
    """בודקת אם יש אלמנט (כמו דלת או חלון) בטווח מסביב לרהיט"""
    fw = int(furniture["width_grid"])
    fd = int(furniture["depth_grid"])
    fz = slot["z"]
    fh = int(furniture.get("high", 1))

    furniture_cells = set(
        (slot["x"] + dx, slot["y"] + dy)
        for dx in range(fw)
        for dy in range(fd)
    )

    checked = set()
    for x, y in furniture_cells:
        for ox in range(-radius, radius + 1):
            for oy in range(-radius, radius + 1):
                cx, cy = x + ox, y + oy
                if (cx, cy) in checked or (cx, cy) in furniture_cells:
                    continue
                checked.add((cx, cy))

                s = next((s for s in floor if s["x"] == cx and s["y"] == cy), None)
                if s:
                    for prop in s.get("properties", []):
                        val = str(prop.get("value", "")).strip().lower()
                        if val == element:
                            if not check_z:
                                return True
                            elif fz + fh > s["z"]:
                                return True
    return False


#****
def calculate_suitability_score(slot, furniture, floor):
    """מחשב ציון לפי מרחקים מרהיטים, דלתות וחלונות"""
    center = get_furniture_center(slot, furniture)
    score = 0
    score += get_distance_score_to_furniture(center)
    score += get_distance_score_to_elements(center, floor, "door")
    score += get_distance_score_to_elements(center, floor, "window")
    return score

def get_furniture_center(slot, furniture):
    """מחזירה את מרכז הרהיט """
    return (
        slot["x"] + int(furniture["width_grid"]) // 2,
        slot["y"] + int(furniture["depth_grid"]) // 2,
    )

def manhattan_distance(p1, p2):
    """מרחק בין שתי נקודות"""
    return abs(p1[0] - p2[0]) + abs(p1[1] - p2[1])

def get_distance_score_to_furniture(center):
    """מרחק מינימלי למרכזי רהיטים קיימים"""
    if not action_stack:
        return 0
    distances = [
        manhattan_distance(center, get_furniture_center(placed_slot, placed_furniture))
        for placed_furniture, placed_slot in action_stack
    ]
    return min(distances)

def get_distance_score_to_elements(center, floor, element_type):
    """מרחק מינימלי בין המרכז לאלמנט (דלת/חלון)"""
    element_slots = [
        s for s in floor if any(
            isinstance(p, dict) and p.get("value", "").lower() == element_type for p in s.get("properties", [])
        )
    ]
    if not element_slots:
        return 10  # ניקוד בסיסי כשאין אלמנט

    distances = [manhattan_distance(center, (s["x"], s["y"])) for s in element_slots]
    return min(distances)


#TODO לבדוק שעובד והגיוני
def handle_no_possible_slots(f, furniture, possible_location, floor):
    """מטפלת במקרה שבו לא נמצאו משבצות מתאימות לרהיט"""
    cancel_action(f, furniture, floor)
    if not possible_location:
        is_possible = check_last()
        if not is_possible:
            raise ValueError("לא נמצאה התאמה לחדר זה")
        return True
    else:
        prev_furniture, prev_slot, prev_possible_slots = possible_location.pop()
        remove_furniture(prev_furniture, prev_slot, f, furniture, floor)
        if prev_possible_slots:
            possible_location.append((prev_furniture, prev_slot, prev_possible_slots))
            furniture.insert(0, prev_furniture)
        return False



def cancel_action(furniture_item, furniture, floor):
    """ביטול הפעולה האחרונה"""
    if not action_stack:
        return
    #prev_furniture, prev_slot, prev_possible_slots = action_stack.pop()
    prev_furniture, prev_slot = action_stack.pop()
    remove_furniture(prev_furniture, prev_slot, furniture_item, furniture, floor)


def check_last():
    """החזרת הפעולה האחרונה"""
    return bool(action_stack)


#*****
def remove_furniture(prev_furniture, prev_slot, furniture_item, furniture, floor):
    """מסירה רהיט מהמשבצת שבה היה מונח ומחזירה את המשבצת למצב 'פנוי'"""
    # חישוב הגבולות של הרהיט
    x_end = prev_slot["x"] + int(prev_furniture["width_grid"])
    y_end = prev_slot["y"] + int(prev_furniture["depth_grid"])
    z_end = prev_slot["z"] + int(prev_furniture["high"])

    # עבור כל המיקומים של הרהיט, עדכן את המשבצות בהתאם
    clear_furniture_area(prev_slot, {
        "width": int(prev_furniture["width_grid"]),
        "depth": int(prev_furniture["depth_grid"]),
        "high": int(prev_furniture["high"])
    }, floor)


def clear_furniture_area(start_slot, dimensions, floor):
    """ניקוי השטח בו היה מונח הרהיט"""
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
        best_entry = max(possible_location, key=lambda entry: entry[2])
        location_data = best_entry[1]
        if not isinstance(location_data, dict):
            raise TypeError("המיקום אינו מילון!")
        return location_data

    except Exception as e:
        return None


def locate(optimal_slot, furniture, floor):
    """מיקום הרהיט בפועל"""
    start_x, start_y, start_z = optimal_slot["x"], optimal_slot["y"], optimal_slot["z"]
    width = int(furniture["width_grid"])
    depth = int(furniture["depth_grid"])
    height = int(furniture["high"])
    f_type = furniture["type"].lower().strip()

    new_property = {
        "_id": 31,
        "value": "furniture",
        "furniture": f_type
    }

    for x in range(start_x, start_x + width):
        for y in range(start_y, start_y + depth):
            slot = next((s for s in floor if s["x"] == x and s["y"] == y), None)

            if slot:
                slot["z"] = height
                if "properties" not in slot:
                    slot["properties"] = []
                slot["properties"].append(new_property)
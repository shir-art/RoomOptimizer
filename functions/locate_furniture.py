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



features = get_features_collection()
floor_collection = get_floor_collection()
#floor = list(floor_collection.find())
properties = get_properties_collection()
requests = get_requests_collection()
suitability = get_suitability_collection()
users = get_users_collection()
# משתנים שונים
action_stack = []  # מחסנית לשמירת הפעולות עבור רהיט שמוקם
suitability_score = None  # ציון התאמה לרהיט


def Place_furniture(furniture, base_floor):
    possible_location = []
    flag = False
    failed = False
    #local_action_stack = []

    for f in furniture:
        possible_location = []
        if not check_furniture_fits_floor(f):
            continue
        possible_slots = get_possible_slots(f, possible_location, base_floor)
        if not possible_slots:
            if not handle_no_possible_slots(f, furniture, possible_location, base_floor):
                continue
        if not possible_location:
            failed = True
            continue
        optimal = find_optimal(possible_location)
        locate(optimal, f, base_floor)
        #action_stack.append((f, optimal, possible_slots))
        action_stack.append((f, optimal))

    #save_room_to_db(furniture_list=action_stack, floor_layout = base_floor)
    #display_floor_3d(base_floor)

    return base_floor



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
def get_possible_slots(f, possible_location, floor):
    possible_slots = []
    for i, slot in enumerate(floor):
        x = Location_matching_check(f['features'], slot, f, possible_location, floor)
        if x not in [True, False]:
            i = next((index for index, s in floor if s["properties"].get("X") == x), i)
        if x == True:
            possible_slots.append(slot)
    return possible_slots

#TODO לבדוק שעובד והגיוני
"מטפלת במקרה שבו לא נמצאו משבצות מתאימות לרהיט"
def handle_no_possible_slots(f, furniture, possible_location, floor):
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


def Location_matching_check(furniture_features, start_slot, furniture, possible_location, floor):
    # קריאה לפונקציה לבדוק אם המשבצת מתאימה
    if not is_slot_suitable(furniture_features, start_slot["properties"]):
        return False
    # קריאה לפונקציה check_neighbors כדי לבדוק את השכנים
    x = check_neighbors(start_slot, furniture, possible_location, floor)
    if not x:
        return False
    # חישוב ציון התאמה על סמך ההתאמות
    return x


#בדיקת התאמת משבצת
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
    if 24 in slot_properties:
        return False
    for feature in furniture_features:
        required_id = feature
        if required_id != "1":
            flag = False
        if required_id in slot_prop_ids:
            flag = True
            # להוסיף עצירה
        return flag


#בדיקת שכנים
def check_neighbors(slot, furniture, possible_location, floor):
    """
    בודקת אם כל השכנים במימדים של הרהיט, כולל גובה, מתאימים למיקום
    """
    if is_too_close_to_existing_furniture(slot, furniture):
        return False
    if not is_within_floor_bounds(slot, furniture, floor):
        return False
    if has_invalid_neighbors(slot, furniture, floor):
        return False
    if has_invalid_property_32(slot, furniture, floor):
        return False
    if not is_adjacent_to_wall(slot, furniture, floor):
        return False
    suitability_score = calculate_suitability_score(slot, furniture, floor)
    possible_location.append((furniture, slot, suitability_score))
    return True


"בודק האם הרהיט קרוב מדי לרהיטים קיימים (פחות ממרחק מינימלי)"
def is_too_close_to_existing_furniture(slot, furniture):
    MIN_DISTANCE = 2
    new_x1 = slot["x"]
    new_y1 = slot["y"]
    new_x2 = new_x1 + int(furniture["width_grid"]) - 1
    new_y2 = new_y1 + int(furniture["depth_grid"]) - 1

    #for placed_furniture, placed_slot, _ in action_stack:
    for placed_furniture, placed_slot in action_stack:

        placed_x1 = placed_slot["x"] - MIN_DISTANCE
        placed_y1 = placed_slot["y"] - MIN_DISTANCE
        placed_x2 = placed_slot["x"] + int(placed_furniture["width_grid"]) + MIN_DISTANCE - 1
        placed_y2 = placed_slot["y"] + int(placed_furniture["depth_grid"]) + MIN_DISTANCE - 1

        if not (new_x2 < placed_x1 or new_x1 > placed_x2 or new_y2 < placed_y1 or new_y1 > placed_y2):
            return True
    return False


"בודק שהרהיט לא חורג מהגבולות של המטריצה בכל שלושת הצירים"
def is_within_floor_bounds(slot, furniture, floor):
    min_x = min(s["x"] for s in floor)
    max_x = max(s["x"] for s in floor)
    min_y = min(s["y"] for s in floor)
    max_y = max(s["y"] for s in floor)
    min_z = min(s["z"] for s in floor)
    max_z = max(s["z"] for s in floor)

    for dx in range(int(furniture["width_grid"])):
        for dy in range(int(furniture["depth_grid"])):
            for dz in range(int(furniture["high"])):
                if not (min_x <= slot["x"] + dx <= max_x and
                        min_y <= slot["y"] + dy <= max_y and
                        min_z <= slot["z"] + dz <= max_z):
                    return False
    return True


def has_invalid_neighbors(slot, furniture, floor):
    furniture_width = int(furniture["width_grid"])
    furniture_depth = int(furniture["depth_grid"])
    furniture_z = slot["z"]
    furniture_x = slot["x"]
    furniture_y = slot["y"]
    furniture_height = int(furniture.get("high", 1))

    for dx in range(furniture_width):
        for dy in range(furniture_depth):
            x = slot["x"] + dx
            y = slot["y"] + dy

            # בדיקה שאין קיר בכל גובה באותו x,y
            for s in floor:
                if s["x"] == x and s["y"] == y:
                    for prop in s.get("properties", []):
                        val = str(prop.get("value", "")).strip().lower()
                        if val == "wall":
                            return True
                        if val == "socket":
                            socket_z = s["z"]
                            furniture_top = furniture_z + furniture_height
                            if furniture_top > socket_z:
                                return True

            # בדיקה לדלת/חלון ברדיוס 2 כולל אלכסון - רק בגובה של הרהיט
            for offset_x in range(-2, 3):
                for offset_y in range(-2, 3):
                    check_x = x + offset_x
                    check_y = y + offset_y

                    s = next((s for s in floor if s["x"] == check_x or s["y"] == check_y ), None)
                    if s:
                        for prop in s.get("properties", []):
                            val = str(prop.get("value", "")).strip().lower()
                            if val == "door":
                                return True
                            #if val == "window":
                                #window_z = s["z"]
                                #dx = abs(furniture_x - s["x"])
                                #dy = abs(furniture_y - s["y"])
                                #distance = max(dx, dy)
                                #furniture_top = furniture_z + furniture_height

                                #if distance <= 3 and furniture_top > window_z:
                                  #  return True
                for dx in range(furniture_width):
                    for dy in range(furniture_depth):
                        furniture_x = slot["x"] + dx
                        furniture_y = slot["y"] + dy

                        # בדיקה אם יש חלון בטווח 3 שמוסתר ע"י הרהיט
                        for offset_x in range(-3, 3):
                            for offset_y in range(-3, 3):
                                check_x = furniture_x + offset_x
                                check_y = furniture_y + offset_y

                                neighbors = [s for s in floor if s["x"] == check_x and s["y"] == check_y]
                                for s in neighbors:
                                    for prop in s.get("properties", []):
                                        val = str(prop.get("value", "")).strip().lower()
                                        if val == "window" :
                                            window_z = s["z"]
                                            furniture_top = furniture_z + furniture_height
                                            if furniture_top > window_z:
                                                return True


    return False





"הפונקציה בודקת האם יש בעיה בערך של תכונה 32-גובה פנוי עבור הרהיט והמשבצת"
def has_invalid_property_32(slot, furniture, floor):
    #property_32_value = extract_property_32(slot)
    #if property_32_value is None:
        #return False
    # בדיקה חדשה: האם יש שקע או חלון מתחת לגובה הרהיט
    for dz in range(int(furniture["high"]) + 1):
        same_xy_slots = [s for s in floor if s["x"] == slot["x"] and s["y"] == slot["y"] and s["z"] == (slot["z"] + dz)]
        if same_xy_slots == slot:
            continue
        for s in same_xy_slots:
            for prop in s.get("properties", []):
                if isinstance(prop, dict):
                    val = str(prop.get("value", "")).strip().lower()
                    if val in ["socket", "window"]:
                        return True

    return False
    #(
        #is_furniture_too_high(furniture, property_32_value)
        #or not is_slot_suitable(furniture["features"], slot["properties"])
    #)

"מחפשת ומחזירה את הערך של תכונה 32 מתוך רשימת התכונות של המשבצת (אם קיים)"
def extract_property_32(slot):
    for prop in slot["properties"]:
        if isinstance(prop, dict) and "32" in prop:
            return prop["32"]
    return None

"בודקת אם הרהיט גבוה מדי ביחס לערך של תכונה 32"
def is_furniture_too_high(furniture, property_32_value):
    return int(furniture["high"]) > property_32_value


#בדיקה האם המשבצת צמודה לקיר
def is_adjacent_to_wall(slot, furniture, floor):
    """
    בודק לפי התכונה של הרהיט:
    - אם צריך להיות צמוד לקיר (near_wall / תכונה 15) – בודק שיש קיר ליד.
    - אם צריך להיות במרכז (in_the_center / תכונה 14) – בודק שאין קיר ליד.
    - אם אין תכונה כזו – מחזיר True כברירת מחדל.
    """
    print("features:", furniture.get("features"))

    feature_ids = furniture.get("features", [])

    if 15 in feature_ids:
        return check_adjacent_to_wall(slot, furniture, floor)
    elif 14 in feature_ids:
        return not check_adjacent_to_wall(slot, furniture, floor)

    return True  # אין דרישה לקיר – מותר למקם בכל מיקום


def check_adjacent_to_wall(slot, furniture, floor):
    x0, y0 = slot["x"], slot["y"]
    width = int(furniture["width_grid"])
    depth = int(furniture["depth_grid"])

    for dx in range(width):
        for dy in range(depth):
            x = x0 + dx
            y = y0 + dy

            neighbors = [(x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)]

            for nx, ny in neighbors:
                neighbor_slots = [s for s in floor if s["x"] == nx and s["y"] == ny]

                for s in neighbor_slots:
                    for prop in s.get("properties", []):
                        if isinstance(prop, dict) and prop.get("value") == 'wall':
                            return True
    return False


def calculate_suitability_score(slot, furniture, floor):
    """
    מחשבת ציון לפי מרחקים מרהיטים, חלונות ודלתות.
    ככל שהרהיט רחוק יותר - הציון גבוה יותר.
    """
    score = 0

    score += get_distance_score_to_furniture(slot, furniture)
    score += get_distance_score_to_elements(slot, furniture, floor, element_type="door")
    score += get_distance_score_to_elements(slot, furniture, floor, element_type="window")

    return score


def get_distance_score_to_furniture(slot, furniture):
    """
    ככל שהרהיט רחוק יותר מרהיטים קיימים - הציון גבוה יותר
    """
    new_center = (
        slot["x"] + int(furniture["width_grid"]) // 2,
        slot["y"] + int(furniture["depth_grid"]) // 2
    )

    min_distance = float("inf")
    if not action_stack:
        return 0
    #for placed_furniture, placed_slot, _ in action_stack:
    for placed_furniture, placed_slot in action_stack:
        placed_center = (
            placed_slot["x"] + int(placed_furniture["width_grid"]) // 2,
            placed_slot["y"] + int(placed_furniture["depth_grid"]) // 2
        )
        dist = abs(new_center[0] - placed_center[0]) + abs(new_center[1] - placed_center[1])
        if dist < min_distance:
            min_distance = dist

    return min_distance


def get_distance_score_to_elements(slot, furniture, floor, element_type):
    """
    מחשבת מרחק מינימלי בין הרהיט לבין אלמנט מסוג מסוים (חלון / דלת)
    """
    new_center = (
        slot["x"] + int(furniture["width_grid"]) // 2,
        slot["y"] + int(furniture["depth_grid"]) // 2
    )

    element_slots = [
        s for s in floor if any(
            isinstance(p, dict) and p.get("value", "").lower() == element_type for p in s.get("properties", [])
        )
    ]

    if not element_slots:
        return 10 #ניקוד בסיסי כשאין אלמנט(כמעט אין סיכוי למקרה כזה)

    min_distance = min(
        abs(new_center[0] - s["x"]) + abs(new_center[1] - s["y"]) for s in element_slots
    )

    return min_distance


"ביטול הפעולה האחרונה"
def cancel_action(furniture_item, furniture, floor):
    if not action_stack:
        return
    #prev_furniture, prev_slot, prev_possible_slots = action_stack.pop()
    prev_furniture, prev_slot = action_stack.pop()
    remove_furniture(prev_furniture, prev_slot, furniture_item, furniture, floor)

    #if prev_possible_slots:

        #action_stack.append((prev_furniture, prev_slot, prev_possible_slots))
    # sorted_furniture_list.insert(0, prev_furniture)
    #else:
        #return


"מסירה רהיט מהמשבצת שבה היה מונח ומחזירה את המשבצת למצב 'פנוי'"
def remove_furniture(prev_furniture, prev_slot, furniture_item, furniture, floor):
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

    # הסרת הרהיט מתוך רשימת הרהיטים
    sorted_furniture_list = [f for f in furniture if
                             not (isinstance(f, dict) and f["_id"] == prev_furniture["_id"])]
    # return sorted_furniture_list
# להוסיף בדיקה מעמיקה


#ניקוי השטח בו היה מונח הרהיט
def clear_furniture_area(start_slot, dimensions, floor):
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
        print(f"❌ שגיאה: {type(e).__name__} - {e}")
        return None


def locate(optimal_slot, furniture, floor):
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
    #action_stack.append((furniture, optimal_slot))



def update_slot_with_furniture(slot, furniture):
    slot["properties"] = [{"_id": 2, "value": "occupied"}]
    slot["properties"].append({
        "_id": 31,
        "value": "furniture",
        "furniture": furniture["_id"]
    })


def check_last():  # בדיקה האם קיים פתרון על ידי בדיקת האיבר הראשון במחסנית
    return bool(action_stack)


#שמירת החדר הסופי ברשימת החדרים של המשתמש
def save_room_to_db(furniture_list, floor_layout):
    room_data = {
        "user_id": userDetails ,
        "furniture_list": furniture_list,
        "floor_layout": floor_layout,
        "date": datetime.today().strftime('%Y-%m-%d %H:%M')

    }
    requests.insert_one(room_data)


def display_floor_3d(floor):
    max_x = max(slot['x'] for slot in floor) + 1
    max_y = max(slot['y'] for slot in floor) + 1

    value_to_color = {
        'wall': 0,
        'empty': 1,
        'null': 2,
        'wardrobe3': 3,
        'wardrobe4': 4,
        'wardrobe5': 5,
        'socket': 6,
        'door': 7,
        'window': 8
    }

    colors = ['black', 'white', 'white', 'coral', 'cyan', 'crimson', 'orchid', 'gray', 'blue']
    legend_labels = ['Wall', 'Empty', 'null', 'wardrobe3', 'wardrobe4', 'wardrobe5', 'socket', 'Door', 'Window']

    _x_opq, _y_opq, _z_opq, dx_opq, dy_opq, dz_opq, colors_opq = [], [], [], [], [], [], []
    _x_trn, _y_trn, _z_trn, dx_trn, dy_trn, dz_trn, colors_trn = [], [], [], [], [], [], []

    for slot in floor:
        x, y, z = slot['x'], slot['y'], slot.get('z', 0)
        props = slot.get('properties', [])

        furniture_type = None
        for p in props:
            if isinstance(p, dict) and p.get('value', '') == 'furniture':
                furniture_type = str(p.get('furniture', '')).lower().strip()

        cell_value = 0
        if furniture_type:
            if furniture_type not in value_to_color:
                value_to_color[furniture_type] = len(value_to_color)
                new_color = np.random.choice(['yellow', 'purple', 'brown', 'pink', 'cyan', 'olive', 'teal'])
                colors.append(new_color)
                legend_labels.append(furniture_type.capitalize())

            cell_value = value_to_color[furniture_type]
        else:
            for key, val in value_to_color.items():
                if key in [str(p.get('value', '')).strip().lower() for p in props]:
                    cell_value = val
                    break

        color = colors[cell_value] if cell_value < len(colors) else 'gray'
        x_list, y_list, z_list = [x], [y], [0]
        dx_list, dy_list, dz_list = [1], [1], [z if z > 0 else 0.01]

        if legend_labels[cell_value].lower() == "wall":
            _x_trn += x_list
            _y_trn += y_list
            _z_trn += z_list
            dx_trn += dx_list
            dy_trn += dy_list
            dz_trn += dz_list
            colors_trn.append(color)
        else:
            _x_opq += x_list
            _y_opq += y_list
            _z_opq += z_list
            dx_opq += dx_list
            dy_opq += dy_list
            dz_opq += dz_list
            colors_opq.append(color)

    fig = plt.figure(figsize=(15, 15))
    ax = fig.add_subplot(111, projection='3d')
    # ציור קירות שקופים עם משטח
    wall_coords = [(s["x"], s["y"]) for s in floor if any(p.get("value") == "wall" for p in s.get("properties", []))]

    if wall_coords:
        wall_x, wall_y = zip(*wall_coords)
        wall_z = np.full(len(wall_x), 1.0)  # גובה הקיר (ניתן לשנות)

        wall_grid_x = np.array(wall_x)
        wall_grid_y = np.array(wall_y)
        wall_grid_z = np.array(wall_z)

        # ציור משטח שקוף
        ax.plot_trisurf(wall_grid_x, wall_grid_y, wall_grid_z, color='black', alpha=0.1, shade=False)


    ax.bar3d(_x_trn, _y_trn, _z_trn, dx_trn, dy_trn, dz_trn, color=colors_trn, alpha=0.3, zsort='average')


    ax.bar3d(_x_opq, _y_opq, _z_opq, dx_opq, dy_opq, dz_opq, color=colors_opq, alpha=1.0, zsort='average')

    ax.set_xticks(np.arange(max_x))
    ax.set_yticks(np.arange(max_y))
    ax.set_zticks([])
    ax.set_xlabel('X')
    ax.set_ylabel('Y')
    ax.set_zlabel('Height')

    patches = [mpatches.Patch(color=colors[i], label=legend_labels[i]) for i in range(len(colors))]
    ax.legend(handles=patches, bbox_to_anchor=(1.05, 1), loc='upper left')

    plt.title("3D Room Layout")
    plt.tight_layout()
    plt.show()











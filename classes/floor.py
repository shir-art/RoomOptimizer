
class Floor:
    def __init__(self,_id, x, y, z, properties, suitability, furniture_type):
        self.floor = []  # רשימת המשבצות על הרצפה
        self.x=x
        self.y=y
        self.z=z
        self.suitability = suitability
        self.furniture_type = furniture_type


    # def add_slot(self, slot):
    #     self.floor.append(slot)
    #
    # def get_slot(self, x, y, z):
    #     return next((s for s in self.floor if s["x"] == x and s["y"] == y and s["z"] == z), None)
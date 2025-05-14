from pymongo import MongoClient

# יצירת לקוח גלובלי פעם אחת
client = MongoClient("mongodb://localhost:27017/")
db = client["Furniture"]

def get_db():
    return db

def get_furniture_collection():
    return db["Furniture"]

def get_floor_collection():
    return db["Floor"]

def get_features_collection():
    return db["Features"]

def get_properties_collection():
    return db["Properties"]

def get_requests_collection():
    return db["Requests"]

def get_suitability_collection():
    return db["Suitability"]

def get_users_collection():
    return db["Users"]


from pymongo import MongoClient

client = MongoClient("mongodb://localhost:27017/")
db = client["Furniture"]

for name in db.list_collection_names():
    print(f"\n📁 Collection: {name}")
    doc = db[name].find_one()
    if doc:
        for key in doc:
            print(f" - {key}: {type(doc[key]).__name__}")
    else:
        print(" (ריק)")

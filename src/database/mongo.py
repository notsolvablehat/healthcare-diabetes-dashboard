import os
from typing import Annotated

from dotenv import load_dotenv
from fastapi import Depends
from pymongo import AsyncMongoClient
from pymongo.asynchronous.database import AsyncDatabase

load_dotenv()


MONGO_DB_URL: str | None = os.getenv("MONGO_DB_URL")

if not MONGO_DB_URL:
    raise RuntimeError("MongoDB connection string not found.")

client = AsyncMongoClient(MONGO_DB_URL)

async def get_mongodb():
    db = client.get_database("health-care-db")

    yield db

async def close_mongodb_connection():
    await client.close()
    print("Closed MongoDB Connection.")

MongoDb = Annotated[AsyncDatabase, Depends(get_mongodb)]

import os
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import db, create_document, get_documents
from schemas import Product as ProductSchema

try:
    from bson import ObjectId
except Exception:
    ObjectId = None  # type: ignore


app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ProductIn(BaseModel):
    title: str
    price: float
    category: str
    description: Optional[str] = None
    image: Optional[str] = None
    in_stock: bool = True


class ProductOut(ProductIn):
    id: str


# -----------------------------
# Health routes
# -----------------------------
@app.get("/")
def read_root():
    return {"message": "Hello from FastAPI Backend!"}


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the backend API!"}


@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }

    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"

            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"

    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    # Check environment variables
    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"

    return response


# -----------------------------
# Helpers
# -----------------------------

def _to_id_str(doc):
    if not doc:
        return doc
    d = dict(doc)
    if d.get("_id") is not None:
        d["id"] = str(d.pop("_id"))
    return d


def _format_product(doc) -> ProductOut:
    d = _to_id_str(doc)
    # Ensure fields exist
    d.setdefault("title", "Untitled")
    d.setdefault("price", 0.0)
    d.setdefault("category", "General")
    d.setdefault("description", None)
    d.setdefault("image", None)
    d.setdefault("in_stock", True)
    return ProductOut(**d)  # type: ignore


# -----------------------------
# Product routes (CRUD)
# -----------------------------
@app.get("/products", response_model=List[ProductOut])
def list_products():
    if db is None:
        return []

    docs = get_documents("product")

    # Seed a few demo products if empty
    if len(docs) == 0:
        seed = [
            ProductSchema(
                title="Carbon Wallet",
                description="Slim carbon fiber wallet with RFID blocking.",
                price=89,
                category="Accessories",
                in_stock=True
            ).model_dump(),
            ProductSchema(
                title="Monochrome Sneakers",
                description="Minimalist sneakers with premium materials.",
                price=159,
                category="Footwear",
                in_stock=True
            ).model_dump(),
            ProductSchema(
                title="Minimal Watch",
                description="Matte black timepiece with sapphire glass.",
                price=129,
                category="Watches",
                in_stock=True
            ).model_dump(),
        ]
        # add images to seed docs
        seed[0]["image"] = "https://images.unsplash.com/photo-1585401586477-2a671e1cae4e?ixlib=rb-4.1.0&w=1600&auto=format&fit=crop&q=80"
        seed[1]["image"] = "https://images.unsplash.com/photo-1519741497674-611481863552?q=80&w=1600&auto=format&fit=crop"
        seed[2]["image"] = "https://images.unsplash.com/photo-1524805444758-089113d48a6d?q=80&w=1600&auto=format&fit=crop"

        for s in seed:
            create_document("product", s)
        docs = get_documents("product")

    return [_format_product(doc) for doc in docs]


@app.post("/products", response_model=ProductOut, status_code=201)
def create_product(product: ProductIn):
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    prod = ProductSchema(
        title=product.title,
        description=product.description,
        price=product.price,
        category=product.category,
        in_stock=product.in_stock,
    ).model_dump()
    prod["image"] = product.image

    inserted_id = create_document("product", prod)
    doc = db["product"].find_one({"_id": ObjectId(inserted_id)}) if ObjectId else db["product"].find_one(sort=[("_id", -1)])
    return _format_product(doc)


@app.get("/products/{product_id}", response_model=ProductOut)
def get_product(product_id: str):
    if db is None:
        raise HTTPException(status_code=503, detail="Database not available")

    doc = None
    if ObjectId:
        try:
            doc = db["product"].find_one({"_id": ObjectId(product_id)})
        except Exception:
            doc = None
    if doc is None:
        raise HTTPException(status_code=404, detail="Product not found")
    return _format_product(doc)


# Simple checkout stub
class CheckoutItem(BaseModel):
    id: str
    title: str
    price: float
    qty: int


class CheckoutRequest(BaseModel):
    items: List[CheckoutItem]
    email: Optional[str] = None


@app.post("/checkout")
def checkout(req: CheckoutRequest):
    total = sum(i.price * i.qty for i in req.items)
    return {
        "status": "ok",
        "message": "Checkout session created",
        "total": round(total, 2),
        "currency": "USD",
        "redirect_url": None,  # integrate Stripe and return url in the future
    }


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)

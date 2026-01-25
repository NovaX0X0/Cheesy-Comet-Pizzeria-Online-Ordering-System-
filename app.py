from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional, Dict, Any, List
from uuid import uuid4

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr


app = FastAPI(title="Pizza Ordering System")


# -----------------------------
# Menu + pricing
# -----------------------------
PizzaSize = Literal["small", "medium", "large"]
CrustType = Literal["thin", "hand_tossed", "deep_dish", "gluten_free"]
SauceType = Literal["tomato", "alfredo", "bbq", "pesto"]
CheeseLevel = Literal["light", "normal", "extra"]
BakeLevel = Literal["normal", "well_done", "light_bake"]
CutStyle = Literal["pie", "square"]
CrustFlavor = Literal["none", "garlic_butter", "sesame"]
Drizzle = Literal["none", "ranch", "hot_honey"]

DrinkType = Literal["none", "coke", "diet_coke", "sprite", "water", "root_beer"]

PRICES = {
    "size": {"small": 10.00, "medium": 13.00, "large": 16.00},
    "crust": {"thin": 0.00, "hand_tossed": 0.00, "deep_dish": 2.00, "gluten_free": 3.00},
    "cheese": {"light": -0.50, "normal": 0.00, "extra": 1.50},
    "crust_flavor": {"none": 0.00, "garlic_butter": 0.75, "sesame": 0.50},
    "drizzle": {"none": 0.00, "ranch": 0.75, "hot_honey": 0.95},
    "topping_each": 1.25,
    "drink": {"none": 0.00, "coke": 2.25, "diet_coke": 2.25, "sprite": 2.25, "water": 1.50, "root_beer": 2.25},
    "tax_rate": 0.0825,
}

TOPPINGS = [
    "pepperoni", "sausage", "bacon", "ham",
    "mushrooms", "onions", "green_peppers", "jalapenos",
    "black_olives", "pineapple", "spinach", "tomatoes"
]


# -----------------------------
# Data models
# -----------------------------
class PizzaCustomization(BaseModel):
    size: PizzaSize
    crust: CrustType
    sauce: SauceType
    cheese: CheeseLevel
    bake: BakeLevel = "normal"
    cut: CutStyle = "pie"
    crust_flavor: CrustFlavor = "none"
    drizzle: Drizzle = "none"
    toppings: List[str] = Field(default_factory=list, description="List of topping names")
    instructions: str = ""

class CartPizzaItem(BaseModel):
    kind: Literal["pizza"] = "pizza"
    name: str = "Custom Pizza"
    customization: PizzaCustomization
    qty: int = Field(ge=1, le=20, default=1)

class CartDrinkItem(BaseModel):
    kind: Literal["drink"] = "drink"
    drink: DrinkType
    qty: int = Field(ge=1, le=20, default=1)

CartItem = CartPizzaItem | CartDrinkItem

class Cart(BaseModel):
    cart_id: str
    items: List[CartItem] = Field(default_factory=list)

class CustomerInfo(BaseModel):
    full_name: str = Field(min_length=2, max_length=80)
    email: Optional[EmailStr] = None
    phone: str = Field(min_length=7, max_length=30)
    address_line1: str = Field(min_length=3, max_length=120)
    address_line2: str = ""
    city: str = Field(min_length=2, max_length=60)
    state: str = Field(min_length=2, max_length=30)
    postal_code: str = Field(min_length=3, max_length=15)

PaymentMethod = Literal["card", "cash", "giftcard"]

class PaymentInfo(BaseModel):
    method: PaymentMethod = "card"

    # Card fields (required if method == "card")
    card_number: Optional[str] = Field(default=None, min_length=12, max_length=19)
    exp_month: Optional[int] = Field(default=None, ge=1, le=12)
    exp_year: Optional[int] = Field(default=None, ge=2024, le=2100)
    cvv: Optional[str] = Field(default=None, min_length=3, max_length=4)
    zip_code: Optional[str] = Field(default=None, min_length=3, max_length=15)

    # Gift card fields (required if method == "giftcard")
    code: Optional[str] = Field(default=None, min_length=4, max_length=64)

    def normalized_card_digits(self) -> str:
        return "".join(ch for ch in (self.card_number or "") if ch.isdigit())

    def validate_required(self) -> None:
        if self.method == "card":
            missing = [k for k in ["card_number", "exp_month", "exp_year", "cvv", "zip_code"] if getattr(self, k) in (None, "")]
            if missing:
                raise HTTPException(status_code=400, detail=f"Missing card fields: {', '.join(missing)}")
        if self.method == "giftcard" and not self.code:
            raise HTTPException(status_code=400, detail="Missing gift card code")

class PlaceOrderRequest(BaseModel):
    cart_id: str
    customer: CustomerInfo
    payment: PaymentInfo


# -----------------------------
# In-memory store (simple)
# -----------------------------
CARTS: Dict[str, Cart] = {}
ORDERS: Dict[str, Dict[str, Any]] = {}


# -----------------------------
# Pricing helpers
# -----------------------------
def validate_toppings(toppings: List[str]) -> List[str]:
    allowed = set(TOPPINGS)
    clean = []
    for t in toppings:
        if t not in allowed:
            raise HTTPException(status_code=400, detail=f"Invalid topping: {t}")
        clean.append(t)
    # remove duplicates, keep order
    dedup = []
    seen = set()
    for t in clean:
        if t not in seen:
            seen.add(t)
            dedup.append(t)
    return dedup

def price_pizza(custom: PizzaCustomization) -> float:
    toppings = validate_toppings(custom.toppings)
    base = PRICES["size"][custom.size]
    crust = PRICES["crust"][custom.crust]
    cheese = PRICES["cheese"][custom.cheese]
    crust_flavor = PRICES["crust_flavor"][custom.crust_flavor]
    drizzle = PRICES["drizzle"][custom.drizzle]
    topping_cost = PRICES["topping_each"] * len(toppings)
    return round(base + crust + cheese + crust_flavor + drizzle + topping_cost, 2)

def price_drink(drink: DrinkType) -> float:
    return round(PRICES["drink"][drink], 2)

def cart_subtotal(cart: Cart) -> float:
    total = 0.0
    for item in cart.items:
        if item.kind == "pizza":
            unit = price_pizza(item.customization)
            total += unit * item.qty
        else:
            unit = price_drink(item.drink)
            total += unit * item.qty
    return round(total, 2)

def enrich_items_with_prices(cart: Cart) -> dict:
    """Return a dict version of the cart where each item includes unit_price and line_total."""
    cart_dict = cart.model_dump()
    enriched = []
    for it in cart.items:
        if it.kind == "pizza":
            unit = price_pizza(it.customization)
        else:
            unit = price_drink(it.drink)
        qty = it.qty or 1
        line_total = round(unit * qty, 2)
        d = it.model_dump()
        d["unit_price"] = round(unit, 2)
        d["line_total"] = line_total
        enriched.append(d)
    cart_dict["items"] = enriched
    return cart_dict

def enrich_order_items(items: list) -> list:
    """Given a list of item dicts (e.g., from cart.model_dump()["items"]),
    attach unit_price and line_total. Coerces nested dicts back into Pydantic models
    for pricing helpers that expect models.
    """
    enriched = []
    for d in items:
        kind = d.get("kind")
        qty = d.get("qty") or 1

        if kind == "pizza":
            custom_raw = d.get("customization") or {}
            # Coerce dict -> PizzaCustomization (pydantic v2)
            try:
                custom_obj = PizzaCustomization.model_validate(custom_raw)
            except Exception:
                custom_obj = PizzaCustomization(**custom_raw)
            unit = price_pizza(custom_obj)
        else:
            unit = price_drink(d.get("drink"))

        d2 = dict(d)
        d2["unit_price"] = round(float(unit), 2)
        d2["line_total"] = round(float(unit) * float(qty), 2)
        enriched.append(d2)
    return enriched


def compute_totals(cart: Cart) -> Dict[str, float]:
    subtotal = cart_subtotal(cart)
    tax = round(subtotal * PRICES["tax_rate"], 2)
    total = round(subtotal + tax, 2)
    return {"subtotal": subtotal, "tax": tax, "total": total}


# -----------------------------
# Mock payment processor
# -----------------------------
def mock_authorize(payment: PaymentInfo, amount: float) -> Dict[str, Any]:
    """Very small mock authorization layer.

    Rules:
    - cash: always approved
    - giftcard: approved if code is present and not "DECLINE"
    - card: decline if expired or ends with 0000
    """
    payment.validate_required()

    if payment.method == "cash":
        return {"status": "approved", "auth_id": "cash", "amount": amount}

    if payment.method == "giftcard":
        if (payment.code or "").strip().upper() == "DECLINE":
            return {"status": "declined", "reason": "Mock gift card declined"}
        return {"status": "approved", "auth_id": "gift_" + uuid4().hex[:10], "amount": amount}

    # card
    now = datetime.utcnow()
    exp_ok = (payment.exp_year > now.year) or (payment.exp_year == now.year and payment.exp_month >= now.month)
    if not exp_ok:
        return {"status": "declined", "reason": "Card expired"}

    digits = payment.normalized_card_digits()
    if digits.endswith("0000"):
        return {"status": "declined", "reason": "Mock decline rule (ends with 0000)"}

    auth_id = "auth_" + uuid4().hex[:12]
    last4 = digits[-4:] if len(digits) >= 4 else "????"
    return {"status": "approved", "auth_id": auth_id, "amount": amount, "card_last4": last4}


# -----------------------------
# API endpoints
# -----------------------------
@app.get("/api/menu")
def get_menu():
    return {
        "toppings": TOPPINGS,
        "drinks": list(PRICES["drink"].keys()),
        "prices": PRICES
    }

@app.post("/api/cart")
def create_cart():
    cart_id = "cart_" + uuid4().hex[:12]
    cart = Cart(cart_id=cart_id, items=[])
    CARTS[cart_id] = cart
    return cart

@app.get("/api/cart/{cart_id}")
def get_cart(cart_id: str):
    cart = CARTS.get(cart_id)
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")
    totals = compute_totals(cart)
    cart_dict = enrich_items_with_prices(cart)
    return {"cart": cart_dict, "totals": totals}
@app.post("/api/cart/{cart_id}/add_pizza")
def add_pizza(cart_id: str, item: CartPizzaItem):
    cart = CARTS.get(cart_id)
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    # validate toppings
    item.customization.toppings = validate_toppings(item.customization.toppings)

    cart.items.append(item)
    return {"cart": cart, "totals": compute_totals(cart)}

@app.post("/api/cart/{cart_id}/add_drink")
def add_drink(cart_id: str, item: CartDrinkItem):
    cart = CARTS.get(cart_id)
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")

    if item.drink == "none":
        raise HTTPException(status_code=400, detail="Drink cannot be 'none' as an item")

    cart.items.append(item)
    return {"cart": cart, "totals": compute_totals(cart)}

class UpdateQtyRequest(BaseModel):
    index: int = Field(ge=0)
    qty: int = Field(ge=1, le=20)

@app.post("/api/cart/{cart_id}/update_qty")
def update_qty(cart_id: str, req: UpdateQtyRequest):
    cart = CARTS.get(cart_id)
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")
    if req.index >= len(cart.items):
        raise HTTPException(status_code=400, detail="Invalid index")

    item = cart.items[req.index]
    item.qty = req.qty
    cart.items[req.index] = item
    return {"cart": cart, "totals": compute_totals(cart)}

class RemoveItemRequest(BaseModel):
    index: int = Field(ge=0)

@app.post("/api/cart/{cart_id}/remove_item")
def remove_item(cart_id: str, req: RemoveItemRequest):
    cart = CARTS.get(cart_id)
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")
    if req.index >= len(cart.items):
        raise HTTPException(status_code=400, detail="Invalid index")

    cart.items.pop(req.index)
    return {"cart": cart, "totals": compute_totals(cart)}

@app.post("/api/cart/{cart_id}/clear")
def clear_cart(cart_id: str):
    cart = CARTS.get(cart_id)
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")
    cart.items = []
    return {"cart": cart, "totals": compute_totals(cart)}

@app.post("/api/orders/place")
def place_order(req: PlaceOrderRequest):
    cart = CARTS.get(req.cart_id)
    if not cart:
        raise HTTPException(status_code=404, detail="Cart not found")
    if not cart.items:
        raise HTTPException(status_code=400, detail="Cart is empty")

    totals = compute_totals(cart)
    payment_result = mock_authorize(req.payment, totals["total"])
    if payment_result["status"] != "approved":
        return {
            "ok": False,
            "message": "Payment declined",
            "payment": payment_result,
            "order_summary": {
                "cart": cart,
                "totals": totals,
                "customer": req.customer
            }
        }

    order_id = "order_" + uuid4().hex[:12]
    summary = {
        "order_id": order_id,
        "created_at_utc": datetime.utcnow().isoformat() + "Z",
        "customer": req.customer.model_dump(),
        "items": enrich_order_items(cart.model_dump()["items"]),
        "totals": totals,
        "payment": payment_result,
        "status": "placed"
    }
    ORDERS[order_id] = summary

    # optional: clear cart after order
    cart.items = []

    return {"ok": True, "order_summary": summary}

@app.get("/api/orders/{order_id}")
def get_order(order_id: str):
    order = ORDERS.get(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return order

# Serve the frontend (robust path regardless of working directory)
BASE_DIR = Path(__file__).resolve().parent
PUBLIC_DIR = BASE_DIR / "public"
app.mount("/", StaticFiles(directory=str(PUBLIC_DIR), html=True), name="public")
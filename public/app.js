// public/app.js

function dollars(n) {
  return `$${Number(n).toFixed(2)}`;
}

async function fetchJson(url, opts) {
  const r = await fetch(url, opts);
  const text = await r.text();
  if (!r.ok) throw new Error(text || `${r.status} ${r.statusText}`);
  if (!text) return {};
  try { return JSON.parse(text); } catch { return {}; }
}

const API = {
  menu() {
    return fetchJson("/api/menu");
  },

  createCart() {
    return fetchJson("/api/cart", { method: "POST" });
  },

  getCart(cartId) {
    return fetchJson(`/api/cart/${cartId}`);
  },

  addPizza(cartId, body) {
    return fetchJson(`/api/cart/${cartId}/add_pizza`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  },

  addDrink(cartId, body) {
    return fetchJson(`/api/cart/${cartId}/add_drink`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  },

  removeItem(cartId, index) {
    return fetchJson(`/api/cart/${cartId}/remove_item`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ index }),
    });
  },

  clearCart(cartId) {
    return fetchJson(`/api/cart/${cartId}/clear`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({}),
    });
  },

  placeOrder(cartId, payload) {
    return fetchJson("/api/orders/place", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cart_id: cartId, ...payload }),
    });
  },
};

async function ensureCart() {
  let cartId = localStorage.getItem("cart_id");

  if (cartId && cartId !== "undefined" && cartId !== "null") {
    try {
      await API.getCart(cartId);
      return cartId;
    } catch {
      localStorage.removeItem("cart_id");
      cartId = null;
    }
  }

  const created = await API.createCart();
  cartId = created.cart_id || created.id;

  if (!cartId) throw new Error("Cart ID missing from createCart response");

  localStorage.setItem("cart_id", cartId);
  return cartId;
}
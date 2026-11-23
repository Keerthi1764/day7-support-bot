
"""
Customer Support Bot (Day 7 Challenge: risk review).

A small Flask app with security fixes and AI monitoring.
"""

import json
import logging
import uuid
import time

from flask import Flask, jsonify, request
from llm import call_llm

app = Flask(__name__)

API_KEY = "sk-demo-4f9a2c71-FAKE-KEY-for-training-only"

logging.basicConfig(
    filename="logs/app.log",
    level=logging.INFO
)

MODEL_NAME = "fake-llm-v1"
COST_PER_TOKEN = 0.0005

ORDERS = {
    "10231": {
        "status": "Shipped",
        "amount": 1299,
        "customer_email": "ravi.kumar@example.com"
    },
    "10232": {
        "status": "Delivered",
        "amount": 499,
        "customer_email": "priya.s@example.com"
    },
    "10233": {
        "status": "Processing",
        "amount": 2499,
        "customer_email": "ravi.kumar@example.com"
    },
}

CUSTOMERS = {
    "ravi.kumar@example.com": {
        "name": "Ravi Kumar",
        "phone": "+91 98480 12345",
        "active": True
    },
    "priya.s@example.com": {
        "name": "Priya Sharma",
        "phone": "+91 99890 67890",
        "active": True
    },
}

REFUNDS = []


# ---------- Tools the LLM can use ----------

def get_order_status(order_id, customer_email):
    order = ORDERS.get(order_id)

    if not order:
        return "Order not found"

    if order["customer_email"] != customer_email:
        return "Order not found"

    return order["status"]


def issue_refund(order_id, amount):
    REFUNDS.append({"order_id": order_id, "amount": amount})
    return f"Refunded Rs {amount} for order {order_id}"


def delete_customer_account(customer_email):
    CUSTOMERS.pop(customer_email, None)
    return f"Deleted account {customer_email}"


TOOLS = {
    "get_order_status": get_order_status,
    "issue_refund": issue_refund,
    "delete_customer_account": delete_customer_account,
}


# ---------- Chat endpoint ----------

@app.post("/chat")
def chat():

    data = request.get_json(silent=True) or {}

    # Generate a unique request ID
    request_id = str(uuid.uuid4())

    email = data.get("customer_email", "")
    message = data.get("message", "")
    customer = CUSTOMERS.get(email, {})

    prompt = (
        "You are a helpful support agent. Reply in JSON with reply, action and args.\n"
        f"Customer name: {customer.get('name')}\n"
        f"Customer email: {email}\n"
        f"Customer phone: {customer.get('phone')}\n"
        f"Customer message: {message}"
    )

    # Measure AI call latency
    start_time = time.perf_counter()

    text, usage = call_llm(prompt, API_KEY)

    end_time = time.perf_counter()

    latency_ms = (end_time - start_time) * 1000

    result = json.loads(text)

    # Get token usage
    input_tokens = usage.get("input_tokens", 0)
    output_tokens = usage.get("output_tokens", 0)

    # Calculate estimated cost
    total_tokens = input_tokens + output_tokens
    estimated_cost = total_tokens * COST_PER_TOKEN

    # Safe AI monitoring log: no customer personal information
    logging.info(
        "AI_MONITOR request_id=%s model=%s latency_ms=%.2f "
        "input_tokens=%d output_tokens=%d estimated_cost=%.4f",
        request_id,
        MODEL_NAME,
        latency_ms,
        input_tokens,
        output_tokens,
        estimated_cost
    )

    action = result.get("action")
    action_result = None
    reply = result.get("reply", "")

    # Fix 1: Refunds must wait for human approval.
    if action == "issue_refund":
        action_result = "Pending human approval"
        reply = "Your refund request has been submitted for human approval."

    # Fix 2: Verify order ownership.
    elif action == "get_order_status":
        args = result.get("args", {})
        order_id = args.get("order_id")
        action_result = get_order_status(order_id, email)

    elif action == "delete_customer_account":
        args = result.get("args", {})

        if args.get("customer_email") == "from_request":
            args["customer_email"] = email

        action_result = TOOLS[action](**args)

    return jsonify({
        "reply": reply,
        "action_result": action_result
    })


if __name__ == "__main__":
    app.run(debug=True)

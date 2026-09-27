"""Safaricom Daraja 3.0 M-Pesa Express (STK Push) integration.

This module provides functions to initiate an M-Pesa Express STK Push payment request
using the Safaricom Daraja API. It handles authentication, request formatting,  
"""

import base64
import os
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from dotenv import load_dotenv

# Load values from the project's .env file during local development.
load_dotenv()

MPESA_ENVIRONMENT = os.getenv("MPESA_ENVIRONMENT", "sandbox").lower()

if MPESA_ENVIRONMENT == "production":
    BASE_URL = "https://api.safaricom.co.ke"
else:
    BASE_URL = "https://sandbox.safaricom.co.ke"

AUTH_URL = f"{BASE_URL}/oauth/v1/generate?grant_type=client_credentials"
STK_PUSH_URL = f"{BASE_URL}/mpesa/stkpush/v1/processrequest"


def _required_setting(name):
    """Return a required environment setting or raise a clear error."""
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"Missing required M-Pesa setting: {name}")
    return value


def get_access_token():
    """Request a short-lived Daraja access token using the app credentials."""
    consumer_key = _required_setting("MPESA_CONSUMER_KEY")
    consumer_secret = _required_setting("MPESA_CONSUMER_SECRET")

    credentials = f"{consumer_key}:{consumer_secret}".encode("utf-8")
    encoded_credentials = base64.b64encode(credentials).decode("utf-8")

    response = requests.get(
        AUTH_URL,
        headers={
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/json",
        },
        timeout=30,
    )
    response.raise_for_status()

    data = response.json()
    token = data.get("access_token")
    if not token:
        raise RuntimeError("Daraja did not return an access token.")

    return token


def _timestamp():
    """Return the timestamp format required by the M-Pesa Express API."""
    return datetime.now(ZoneInfo("Africa/Nairobi")).strftime("%Y%m%d%H%M%S")


def _stk_password(shortcode, passkey, timestamp):
    """Create the Base64 password required by the STK Push request."""
    raw_password = f"{shortcode}{passkey}{timestamp}".encode("utf-8")
    return base64.b64encode(raw_password).decode("utf-8")


def _normalise_phone(phone):
    """Convert common Kenyan phone formats to 254XXXXXXXXX."""
    phone = str(phone).strip().replace(" ", "").replace("-", "")

    if phone.startswith("+254"):
        phone = phone[1:]
    elif phone.startswith("07") or phone.startswith("01"):
        phone = "254" + phone[1:]
    elif phone.startswith("7") or phone.startswith("1"):
        phone = "254" + phone

    if not (phone.isdigit() and len(phone) == 12 and phone.startswith("254")):
        raise ValueError("Phone number must be a valid Kenyan number, e.g. 0712345678 or 254712345678.")

    return phone


def initiate_stk_push(
    phone_number,
    amount,
    account_reference="NexaPark",
    transaction_description="NexaPark parking payment",
    callback_url=None,
):
    """Send an M-Pesa Express STK Push request.

    Returns the decoded Daraja response as a dictionary. This function starts
    the payment prompt; it does not by itself confirm that the customer paid.
    Payment confirmation will be handled by NexaPark's callback route later.
    """
    shortcode = _required_setting("MPESA_SHORTCODE")
    passkey = _required_setting("MPESA_PASSKEY")
    callback_url = callback_url or os.getenv("MPESA_CALLBACK_URL")

    if not callback_url:
        raise RuntimeError("Missing required M-Pesa setting: MPESA_CALLBACK_URL")

    try:
        amount = int(amount)
    except (TypeError, ValueError):
        raise ValueError("M-Pesa amount must be a whole number.")

    if amount <= 0:
        raise ValueError("M-Pesa amount must be greater than zero.")

    phone = _normalise_phone(phone_number)
    timestamp = _timestamp()
    password = _stk_password(shortcode, passkey, timestamp)
    access_token = get_access_token()

    payload = {
        "BusinessShortCode": shortcode,
        "Password": password,
        "Timestamp": timestamp,
        "TransactionType": "CustomerPayBillOnline",
        "Amount": amount,
        "PartyA": phone,
        "PartyB": shortcode,
        "PhoneNumber": phone,
        "CallBackURL": callback_url,
        "AccountReference": account_reference,
        "TransactionDesc": transaction_description,
    }

    response = requests.post(
        STK_PUSH_URL,
        json=payload,
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        timeout=30,
    )

    try:
        data = response.json()
    except ValueError:
        response.raise_for_status()
        raise RuntimeError("Daraja returned an unexpected response.")

    if not response.ok:
        message = (
            data.get("errorMessage")
            or data.get("errorCode")
            or data.get("ResponseDescription")
            or "Daraja request failed."
        )
        raise RuntimeError(message)

    response_code = str(data.get("ResponseCode", ""))

    if response_code and response_code != "0":
        message = (
            data.get("ResponseDescription")
            or data.get("CustomerMessage")
            or "Daraja did not accept the STK Push request."
        )
        raise RuntimeError(message)
    return data

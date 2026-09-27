VALET_FEE = 100
BOOKING_DEPOSIT_RATE = 0.50


def calculate_parking_fee(duration_minutes):
    """Return the base parking fee for a duration in minutes."""
    if duration_minutes <= 30:
        return 0
    if duration_minutes <= 120:
        return 50
    if duration_minutes <= 240:
        return 100
    if duration_minutes <= 360:
        return 300
    return 500


def calculate_fee(duration_minutes, valet=False):
    """Return a complete price breakdown, including optional valet service."""
    duration_minutes = int(duration_minutes)
    if duration_minutes < 0:
        raise ValueError("Duration cannot be negative.")

    parking_fee = calculate_parking_fee(duration_minutes)
    valet_fee = VALET_FEE if valet else 0
    total_price = parking_fee + valet_fee

    return {
        "parking_fee": parking_fee,
        "valet_fee": valet_fee,
        "total_price": total_price,
    }


def calculate_booking_payment(total_price):
    """Calculate the 50% booking deposit and remaining balance."""
    total_price = int(total_price)
    deposit = total_price // 2
    # If a future pricing rule produces an odd amount, keep the two amounts
    # mathematically consistent by assigning the extra shilling to the balance.
    balance = total_price - deposit
    return {
        "total_price": total_price,
        "deposit_amount": deposit,
        "balance_amount": balance,
    }

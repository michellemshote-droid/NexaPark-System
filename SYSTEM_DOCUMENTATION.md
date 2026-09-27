# NexaPark — System Documentation

## 1. Introduction

NexaPark is a **Flask-based web application with a SQLite database** for managing a modern physical car park.

The system supports:

- Normal vehicle entry and exit
- Automatic parking-bay allocation
- Parking-fee calculation
- Online parking pre-booking
- 50% M-Pesa booking deposits
- M-Pesa payment of the remaining exit balance
- Optional valet parking
- Valet pickup requests
- Authenticated administrator management
- Parking, payment, booking, valet and daily reporting records
- A live parking-slot availability view

The application is implemented in Python using Flask. The user interface is built with HTML, CSS and JavaScript, while SQLite provides persistent data storage.

---

# 2. System Actors

NexaPark has two main human actors and one external service actor.

| Actor                         | Role                                                                                                                         |
| ----------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| **Customer / Driver**         | Enters and exits the car park, views availability, makes bookings, pays parking charges, and optionally uses valet services. |
| **Administrator**             | Monitors vehicles, slots, bookings, valet operations, payments, history and reports through the protected admin dashboard.   |
| **Safaricom Daraja / M-Pesa** | External payment service used to initiate STK Push payments and send payment-confirmation callbacks to NexaPark.             |

---

# 3. Use Cases

## 3.1 Customer Use Cases

### UC-01: View Parking Availability

**Actor:** Customer

**Description:**  
The customer can view the current availability of parking bays from the home page.

**Main flow:**

1. Customer opens the NexaPark home page.
2. The application queries the `parking_slots` table.
3. Each bay is displayed with its current status.
4. The customer can see available and occupied bays.

**Related implementation:**

- `app.py` → `home()`
- `database.py` → `get_slots()`
- `/api/slots`

---

## UC-02: Enter the Car Park

**Actor:** Customer

**Description:**  
A driver registers a vehicle at the parking entrance.

**Main flow:**

1. Customer enters the vehicle number plate.
2. Customer selects the vehicle type.
3. NexaPark normalizes the plate number.
4. The system checks whether the vehicle already has an active parking session.
5. The system checks available capacity.
6. Confirmed bookings are considered when determining walk-in capacity.
7. The first available parking bay is selected.
8. A parking session is created.
9. The selected bay is changed from `AVAILABLE` to `OCCUPIED`.
10. If the customer has a valid booking, the booking becomes `CHECKED_IN`.
11. If the booking requested valet service, a valet request is created.
12. The assigned bay and entry time are displayed.

**Related implementation:**

- `app.py` → `/entry`
- `parking.py` → `record_entry()`
- `database.py` → `get_available_slot()`, `get_or_create_vehicle()`

---

## UC-03: Exit the Car Park

**Actor:** Customer

**Description:**  
A driver starts the exit process using the vehicle number plate.

**Main flow:**

1. Customer enters the vehicle plate.
2. NexaPark finds the active parking session.
3. Entry and current time are used to calculate the parking duration.
4. The parking fee is calculated.
5. If valet service was used, the valet fee is included.
6. If the session belongs to a booking, the amount already paid as a deposit is deducted.
7. The remaining balance is displayed.
8. Customer proceeds to payment.

**Related implementation:**

- `app.py` → `/exit`
- `parking.py` → `prepare_exit()`
- `pricing.py` → `calculate_fee()`

---

## UC-04: Pay the Parking Balance

**Actor:** Customer + Safaricom Daraja

**Description:**  
The customer pays the remaining parking balance using M-Pesa.

**Main flow:**

1. NexaPark calculates the outstanding amount.
2. Customer enters an M-Pesa phone number.
3. NexaPark sends an STK Push request through Safaricom Daraja.
4. The transaction is stored as `PENDING`.
5. Customer completes or cancels the M-Pesa prompt.
6. Safaricom sends a callback to `/mpesa/callback`.
7. NexaPark validates the payment amount.
8. A valid payment becomes `PAID`.
9. The parking session is completed.
10. The parking bay is released.
11. The payment is recorded.
12. The customer receives the exit-success result.

**Important:** The code starts and confirms real Daraja STK Push payments when the required M-Pesa configuration is supplied. The actual physical barrier hardware is not connected to the application.

**Related implementation:**

- `app.py` → `pay()`
- `app.py` → `mpesa_callback()`
- `mpesa.py` → `initiate_stk_push()`
- `database.py` → M-Pesa transaction functions
- `parking.py` → `complete_exit()`

---

## UC-05: Pre-book a Parking Space

**Actor:** Customer

**Description:**  
A customer can reserve parking capacity for a future arrival and departure period.

**Main flow:**

1. Customer enters vehicle plate and vehicle type.
2. Customer selects arrival and departure time.
3. Customer may select valet service.
4. NexaPark validates the requested time period.
5. The system calculates the booking price.
6. The required deposit is calculated as 50% of the total.
7. NexaPark checks overlapping bookings against total parking capacity.
8. A booking is created with status `PENDING_PAYMENT`.
9. An M-Pesa STK Push is initiated for the deposit.
10. After successful callback confirmation, the booking becomes `CONFIRMED`.
11. The booking receives a unique reference such as `BK-XXXXXX`.

**Important design decision:**  
NexaPark reserves **parking capacity**, rather than permanently assigning a particular bay during online booking. The actual bay is assigned when the vehicle arrives.

**Related implementation:**

- `app.py` → `/book`
- `parking.py` → `create_booking()`
- `pricing.py` → `calculate_fee()`, `calculate_booking_payment()`

---

## UC-06: Cancel a Booking

**Actor:** Customer

**Description:**  
A customer can cancel a pending or confirmed booking.

**Main flow:**

1. Customer supplies the booking reference.
2. Customer supplies the vehicle plate.
3. NexaPark verifies that both match the same booking.
4. If the booking is `PENDING_PAYMENT` or `CONFIRMED`, it is changed to `CANCELLED`.
5. The booking no longer reserves parking capacity.

**Related implementation:**

- `app.py` → `/book/cancel`
- `parking.py` → `cancel_booking()`

---

## UC-07: Use Valet Drop-off

**Actor:** Customer

**Description:**  
A customer can hand the vehicle to the valet service instead of parking it personally.

**Main flow:**

1. Customer supplies the vehicle plate and vehicle type.
2. Customer may provide a drop-off location/note.
3. NexaPark performs the normal parking-entry process.
4. A valet request is created.
5. The valet request starts with status `PARKED`.

**Related implementation:**

- `app.py` → `/valet/dropoff`
- `parking.py` → `record_valet_dropoff()`

---

## UC-08: Request Valet Pickup

**Actor:** Customer

**Description:**  
A customer can request the return of a vehicle currently under valet management.

**Main flow:**

1. Customer enters the vehicle plate.
2. NexaPark searches for an active valet session.
3. The valet request changes to `RETRIEVING`.
4. The request time is recorded.
5. The valet team can then process the vehicle.

**Related implementation:**

- `app.py` → `/valet/pickup`
- `parking.py` → `request_valet_pickup()`

---

# 4. Administrator Use Cases

## UC-09: Administrator Login

**Actor:** Administrator

The administrator signs in through `/admin/login`.

The system:

1. Finds the administrator by username.
2. Checks whether the account is temporarily locked.
3. Verifies the password hash.
4. Records failed attempts when authentication fails.
5. Locks the account temporarily after repeated failed attempts.
6. Clears failed-attempt counters after successful login.
7. Creates a protected Flask session.

### Security rule

The system allows a maximum of **5 failed login attempts** before a **15-minute temporary lockout**.

Passwords are stored using Werkzeug password hashing rather than plain text.

---

## UC-10: Monitor Vehicles

The administrator can view currently active vehicles, their vehicle types, assigned bays and entry times.

**Implementation:** `/admin/vehicles`

---

## UC-11: Monitor Parking Bays

The administrator can view all parking bays and their current statuses.

**Implementation:** `/admin/slots`

---

## UC-12: Manage Bookings

The administrator can view booking references, statuses, time windows, vehicle details, valet selection and payment amounts.

**Implementation:** `/admin/bookings`

---

## UC-13: Manage Valet Operations

The administrator can:

- View valet requests
- Mark a vehicle as `RETRIEVING`
- Mark a vehicle as `DELIVERED`

**Implementation:** `/admin/valet`

---

## UC-14: View Payment Records

The administrator can view parking payment records, amounts, payment times and payment statuses.

**Implementation:** `/admin/payments`

---

## UC-15: View Parking History

The administrator can view completed and active parking sessions together with entry time, exit time, duration and fee.

**Implementation:** `/admin/history`

---

## UC-16: View Daily Reports

The administrator can view daily statistics including:

- Total parking sessions
- Active sessions
- Completed sessions
- Revenue
- Free visits
- Paid visits

**Implementation:** `/admin/reports`

---

# 5. System Modules

The project is divided into several modules. Each module has a specific responsibility.

## 5.1 `app.py` — Application / Presentation Controller

**Purpose:**  
Acts as the main Flask application and connects the web pages to the business-logic and database modules.

**Main responsibilities:**

- Define HTTP routes
- Receive form data
- Validate request flow
- Call parking and pricing functions
- Manage Flask sessions
- Render HTML templates
- Handle admin routes
- Start M-Pesa payment requests
- Receive M-Pesa callbacks
- Expose the parking-slot API

**Examples of routes:**

```text
/
 /entry
 /exit
 /pay
 /book
 /book/cancel
 /valet/dropoff
 /valet/pickup
 /admin/login
 /admin/dashboard
 /admin/vehicles
 /admin/slots
 /admin/bookings
 /admin/valet
 /admin/payments
 /admin/history
 /admin/reports
 /mpesa/callback
 /api/slots
```

---

## 5.2 `parking.py` — Parking Business Logic

**Purpose:**  
Contains the main operational rules for vehicles, parking sessions, bookings and valet operations.

**Important functions:**

| Function                         | Purpose                                                                       |
| -------------------------------- | ----------------------------------------------------------------------------- |
| `normalise_plate()`              | Standardizes vehicle plate input.                                             |
| `format_duration()`              | Converts minutes into a readable duration.                                    |
| `expire_stale_bookings()`        | Cancels old unpaid bookings and marks expired confirmed bookings as no-shows. |
| `generate_booking_reference()`   | Creates a unique booking reference.                                           |
| `get_active_booking_for_plate()` | Finds a valid booking for a vehicle at the current time.                      |
| `record_entry()`                 | Creates a parking session and assigns a bay.                                  |
| `prepare_exit()`                 | Calculates the current parking charge before payment.                         |
| `complete_exit()`                | Completes the parking session and releases the bay.                           |
| `create_booking()`               | Creates a new parking reservation.                                            |
| `confirm_booking_payment()`      | Confirms a booking after deposit payment.                                     |
| `cancel_booking()`               | Cancels an eligible booking.                                                  |
| `record_valet_dropoff()`         | Records valet entry.                                                          |
| `request_valet_pickup()`         | Starts valet retrieval.                                                       |
| `mark_valet_retrieving()`        | Admin action to mark a valet request as retrieving.                           |
| `mark_valet_delivered()`         | Admin action to mark a vehicle as delivered.                                  |

---

## 5.3 `pricing.py` — Pricing Module

**Purpose:**  
Centralizes parking and valet pricing rules.

**Important functions:**

- `calculate_parking_fee()`
- `calculate_fee()`
- `calculate_booking_payment()`

Keeping pricing separate prevents fee rules from being duplicated throughout the application.

---

## 5.4 `database.py` — Database Access Layer

**Purpose:**  
Creates the SQLite database, performs queries and provides database-related functions to other modules.

**Main responsibilities:**

- Create database tables
- Establish SQLite connections
- Enable foreign-key enforcement
- Initialize 20 parking bays
- Handle schema migration
- Manage admin accounts
- Retrieve parking data
- Retrieve booking data
- Retrieve valet data
- Store payments
- Store M-Pesa transaction records

The module acts as a simple **data-access layer**, keeping SQL operations separate from the main Flask routes.

---

## 5.5 `auth.py` — Authentication Module

**Purpose:**  
Handles administrator authentication.

**Important functions:**

- `authenticate_admin()`
- `validate_password_strength()`
- `ensure_default_admin()`

The module works with the `admins` table and Werkzeug password hashing.

---

## 5.6 `mpesa.py` — M-Pesa / Daraja Integration

**Purpose:**  
Communicates with Safaricom's Daraja API.

**Important functions:**

- `get_access_token()`
- `initiate_stk_push()`
- `_normalise_phone()`
- `_stk_password()`
- `_timestamp()`

The module:

1. Loads M-Pesa configuration from environment variables.
2. Requests a Daraja access token.
3. Normalizes Kenyan phone numbers.
4. Creates the STK password.
5. Sends an STK Push request.
6. Returns the Daraja response to the Flask application.

---

## 5.7 HTML Templates

The `templates/` directory provides the web interface.

### Customer pages

```text
base.html
index.html
entry.html
entry_success.html
exit.html
payment.html
payment_pending.html
exit_success.html
book.html
book_success.html
book_payment_pending.html
book_cancel.html
valet_dropoff.html
valet_dropoff_success.html
valet_pickup.html
```

### Administrator pages

```text
admin/base.html
admin/login.html
admin/dashboard.html
admin/vehicles.html
admin/slots.html
admin/bookings.html
admin/valet.html
admin/payments.html
admin/history.html
admin/reports.html
```

---

## 5.8 Static Files

### `static/css/style.css`

Contains the application's visual styling and layout.

### `static/js/main.js`

Contains client-side JavaScript used by the web interface.

---

# 6. Algorithms

## 6.1 Vehicle Plate Normalization Algorithm

The system normalizes plate numbers before using them in database searches.

### Steps

1. Convert the input to uppercase.
2. Remove leading and trailing whitespace.
3. Collapse repeated spaces.
4. Return the normalized plate.

### Example

```text
"  kda 123a " → "KDA 123A"
```

**Function:** `normalise_plate()`

---

# 6.2 First Available Parking Bay Algorithm

NexaPark uses a simple first-available-bay strategy.

### Steps

1. Query `parking_slots`.
2. Select rows where `status = 'AVAILABLE'`.
3. Sort by `slot_id`.
4. Select the first result.
5. Assign that bay to the new parking session.
6. Change its status to `OCCUPIED`.

Conceptually:

```text
Find AVAILABLE slots
        ↓
Sort by slot ID
        ↓
Select first slot
        ↓
Assign slot to vehicle
        ↓
Set slot = OCCUPIED
```

**Function:** `get_available_slot()`

This is a simple deterministic allocation algorithm.

---

# 6.3 Walk-in Capacity Reservation Algorithm

Pre-booked vehicles must be protected from being displaced by walk-in vehicles.

### Steps

1. Count currently available bays.
2. Count confirmed bookings active at the current time.
3. Calculate:

```text
walk_in_capacity = available_bays - currently_reserved_bays
```

4. If the result is zero or negative, a walk-in vehicle is rejected even if the physical slot table still contains a bay marked available.
5. A vehicle with a valid current booking can proceed.

This prevents walk-in customers from consuming capacity already reserved for confirmed bookings.

---

# 6.4 Booking Overlap Algorithm

When a customer requests a booking, NexaPark checks whether existing bookings overlap the requested time interval.

Two time intervals overlap when:

```text
existing_start < requested_end
AND
existing_end > requested_start
```

The system counts bookings with status:

```text
CONFIRMED
PENDING_PAYMENT
```

If the number of overlapping bookings is equal to or greater than the total number of parking bays, the new booking is rejected.

---

# 6.5 Parking Duration Algorithm

The duration is calculated from entry time to the current exit time.

```text
duration = exit_time - entry_time
```

The result is converted to minutes.

The implementation also prevents a negative duration:

```text
duration_minutes = max(0, calculated_minutes)
```

---

# 6.6 Parking Fee Calculation Algorithm

The parking fee is determined by the number of minutes.

| Duration         | Parking Fee |
| ---------------- | ----------: |
| `<= 30` minutes  |       KSh 0 |
| `<= 120` minutes |      KSh 50 |
| `<= 240` minutes |     KSh 100 |
| `<= 360` minutes |     KSh 300 |
| `> 360` minutes  |     KSh 500 |

The algorithm uses a sequence of conditional comparisons.

**Function:** `calculate_parking_fee()`

---

# 6.7 Valet Fee Algorithm

The system adds a fixed valet charge when valet service is selected.

Current implementation:

```text
VALET_FEE = KSh 100
```

Therefore:

```text
total_price = parking_fee + valet_fee
```

When valet is not selected:

```text
valet_fee = KSh 0
```

---

# 6.8 Booking Deposit Algorithm

The booking deposit is 50% of the calculated total price.

```text
deposit = total_price // 2
balance = total_price - deposit
```

Using integer division ensures that the stored monetary amounts are whole Kenyan shillings.

For an odd total, the extra shilling remains in the final balance.

---

# 6.9 Exit Balance Algorithm

When a pre-booked vehicle exits:

```text
total charge = parking fee + valet fee
```

Then:

```text
amount due = total charge - deposit already paid
```

The system prevents a negative amount:

```text
amount_due = max(0, total_charge - deposit_paid)
```

Therefore the customer does not pay the same booking deposit twice.

---

# 6.10 Booking Expiration Algorithm

The system handles two types of stale booking.

### Pending payment

A `PENDING_PAYMENT` booking is cancelled after the configured 15-minute payment timeout.

### Confirmed booking

A `CONFIRMED` booking whose requested departure time has passed without check-in becomes:

```text
NO_SHOW
```

This releases its capacity reservation.

---

# 6.11 Booking Reference Generation Algorithm

A booking reference is generated in the form:

```text
BK-XXXXXX
```

The six-character suffix is generated using a secure random token.

The system checks the database to ensure that the generated reference is unique.

---

# 6.12 M-Pesa Payment Confirmation Algorithm

NexaPark does not treat an STK Push request as proof of payment.

The process is:

```text
Customer
   ↓
STK Push
   ↓
Daraja accepts request
   ↓
Transaction stored as PENDING
   ↓
Customer completes payment
   ↓
Daraja callback
   ↓
Validate callback
   ↓
Validate amount
   ↓
Mark transaction PAID
   ↓
Complete booking or parking session
```

If the callback result code indicates failure or cancellation, the transaction is marked accordingly.

The system also compares the amount received with the amount expected.

If:

```text
paid_amount != expected_amount
```

the transaction is marked `FAILED`.

---

# 6.13 Valet State-Transition Algorithm

Valet operations use three main states:

```text
PARKED
   ↓
RETRIEVING
   ↓
DELIVERED
```

### Meaning

- `PARKED` — vehicle is under valet management.
- `RETRIEVING` — customer has requested the vehicle and the valet is retrieving it.
- `DELIVERED` — vehicle has been returned to the customer.

---

# 6.14 Admin Login Lockout Algorithm

The authentication system limits repeated failed login attempts.

### Steps

1. Look up the administrator.
2. Check whether the account is currently locked.
3. Verify the password hash.
4. If incorrect, increment `failed_attempts`.
5. When attempts reach 5, set `locked_until` to 15 minutes in the future.
6. Reset failed attempts after a successful login.

---

# 7. Data Structures Used

The project uses several data structures provided by Python, SQLite and Flask.

## 7.1 Dictionaries

Python dictionaries are used extensively for passing structured results between modules and templates.

Example concept:

```python
{
    "success": True,
    "plate": "KDA 123A",
    "slot": "A01",
    "fee": 100
}
```

They are useful because values can be accessed by descriptive keys instead of numeric positions.

Examples in the project include results returned by:

- `record_entry()`
- `prepare_exit()`
- `complete_exit()`
- `create_booking()`
- `calculate_fee()`

---

## 7.2 Lists

Lists are used for collections of records returned from database queries.

For example, functions such as:

```text
get_slots()
get_active_vehicles()
get_payments()
get_history()
get_bookings()
get_valet_requests()
```

return lists of records.

---

## 7.3 Tuples

Tuples are used when supplying parameter values to SQLite queries.

Example:

```python
conn.execute(
    "SELECT * FROM vehicles WHERE plate_number=?",
    (plate,)
)
```

Tuples are appropriate here because SQL parameter values are passed as an ordered collection.

---

## 7.4 SQLite Rows

The database connection uses:

```python
conn.row_factory = sqlite3.Row
```

This allows database records to be accessed using column names.

For example:

```python
row["plate_number"]
row["slot_id"]
row["entry_time"]
```

This improves readability compared with using numeric column indexes.

---

## 7.5 Flask Session

The Flask session is used to temporarily associate a browser session with operations such as:

- Logged-in administrator
- Pending exit session
- Pending vehicle plate
- M-Pesa payment flow

Examples include:

```text
session["admin_id"]
session["admin_username"]
session["pending_exit"]
session["pending_plate"]
```

---

## 7.6 Relational Tables

The main persistent data structure is the relational SQLite database.

Relationships are represented using:

- Primary keys
- Foreign keys
- Unique constraints
- Check constraints

---

# 8. Database Design

NexaPark uses **SQLite**.

Database file:

```text
database/parking.db
```

SQLite is suitable for the current application because it is serverless, lightweight and does not require a separate database server.

---

# 9. Database Tables

The implemented database contains the following main tables.

## 9.1 `admins`

Stores administrator accounts.

| Column            | Type    | Purpose                       |
| ----------------- | ------- | ----------------------------- |
| `admin_id`        | INTEGER | Primary key                   |
| `username`        | TEXT    | Unique administrator username |
| `password_hash`   | TEXT    | Hashed password               |
| `failed_attempts` | INTEGER | Failed login counter          |
| `locked_until`    | TEXT    | Temporary lockout timestamp   |

---

## 9.2 `vehicles`

Stores registered vehicles.

| Column         | Type    | Purpose                     |
| -------------- | ------- | --------------------------- |
| `vehicle_id`   | INTEGER | Primary key                 |
| `plate_number` | TEXT    | Unique vehicle registration |
| `vehicle_type` | TEXT    | Vehicle category            |

A vehicle can have multiple parking sessions over time.

---

## 9.3 `parking_slots`

Stores the physical parking bays managed by the application.

| Column        | Type    | Purpose                           |
| ------------- | ------- | --------------------------------- |
| `slot_id`     | INTEGER | Primary key                       |
| `slot_number` | TEXT    | Unique bay identifier such as A01 |
| `status`      | TEXT    | `AVAILABLE` or `OCCUPIED`         |

The database initializes **20 parking bays** when the slot table is empty.

---

## 9.4 `parking_sessions`

Stores each vehicle's actual parking visit.

| Column             | Type    | Purpose                              |
| ------------------ | ------- | ------------------------------------ |
| `session_id`       | INTEGER | Primary key                          |
| `vehicle_id`       | INTEGER | Foreign key to `vehicles`            |
| `slot_id`          | INTEGER | Foreign key to `parking_slots`       |
| `entry_time`       | TEXT    | Vehicle entry timestamp              |
| `exit_time`        | TEXT    | Vehicle exit timestamp               |
| `duration_minutes` | INTEGER | Parking duration                     |
| `fee`              | INTEGER | Final parking + applicable valet fee |
| `status`           | TEXT    | `ACTIVE` or `COMPLETED`              |

---

## 9.5 `payments`

Stores final parking-session payment records.

| Column           | Type    | Purpose                               |
| ---------------- | ------- | ------------------------------------- |
| `payment_id`     | INTEGER | Primary key                           |
| `session_id`     | INTEGER | Unique foreign key to parking session |
| `amount`         | INTEGER | Amount recorded for final payment     |
| `payment_time`   | TEXT    | Payment timestamp                     |
| `payment_status` | TEXT    | Payment state                         |

For a booked vehicle, the final payment record represents the amount due after the booking deposit has been accounted for.

---

## 9.6 `bookings`

Stores online parking reservations.

| Column            | Type    | Purpose                               |
| ----------------- | ------- | ------------------------------------- |
| `booking_id`      | INTEGER | Primary key                           |
| `reference`       | TEXT    | Unique booking reference              |
| `vehicle_id`      | INTEGER | Foreign key to vehicle                |
| `session_id`      | INTEGER | Linked parking session after check-in |
| `requested_start` | TEXT    | Requested arrival time                |
| `requested_end`   | TEXT    | Requested departure time              |
| `status`          | TEXT    | Booking state                         |
| `created_at`      | TEXT    | Creation timestamp                    |
| `valet_requested` | INTEGER | Boolean-style flag                    |
| `parking_fee`     | INTEGER | Calculated parking price              |
| `valet_fee`       | INTEGER | Valet charge                          |
| `total_price`     | INTEGER | Total booking price                   |
| `deposit_amount`  | INTEGER | Required 50% deposit                  |
| `amount_paid`     | INTEGER | Deposit amount confirmed as paid      |

Possible booking statuses:

```text
PENDING_PAYMENT
CONFIRMED
CHECKED_IN
CANCELLED
NO_SHOW
```

---

## 9.7 `valet_requests`

Stores valet operations associated with parking sessions.

| Column                | Type    | Purpose                               |
| --------------------- | ------- | ------------------------------------- |
| `valet_id`            | INTEGER | Primary key                           |
| `session_id`          | INTEGER | Unique foreign key to parking session |
| `drop_off_location`   | TEXT    | Customer's drop-off information       |
| `pickup_requested_at` | TEXT    | Pickup request timestamp              |
| `pickup_completed_at` | TEXT    | Delivery timestamp                    |
| `status`              | TEXT    | Valet state                           |

Possible states:

```text
PARKED
RETRIEVING
DELIVERED
```

---

## 9.8 `mpesa_transactions`

Stores Daraja payment transactions.

| Column                 | Type    | Purpose                             |
| ---------------------- | ------- | ----------------------------------- |
| `transaction_id`       | INTEGER | Primary key                         |
| `session_id`           | INTEGER | Related parking session             |
| `booking_id`           | INTEGER | Related booking                     |
| `payment_type`         | TEXT    | `BOOKING_DEPOSIT` or `EXIT_BALANCE` |
| `checkout_request_id`  | TEXT    | Unique Daraja checkout identifier   |
| `merchant_request_id`  | TEXT    | Daraja merchant request identifier  |
| `phone_number`         | TEXT    | Customer M-Pesa number              |
| `amount`               | INTEGER | Expected payment                    |
| `account_reference`    | TEXT    | NexaPark payment reference          |
| `status`               | TEXT    | Payment state                       |
| `mpesa_receipt_number` | TEXT    | Safaricom receipt                   |
| `result_code`          | INTEGER | Daraja result code                  |
| `result_description`   | TEXT    | Daraja result description           |
| `created_at`           | TEXT    | Transaction creation time           |
| `completed_at`         | TEXT    | Completion time                     |

Possible transaction states:

```text
PENDING
PAID
FAILED
CANCELLED
```

---

# 10. Database Relationships

The main relationships are:

```text
ADMIN
  └── manages the system

VEHICLE
  └──< PARKING_SESSION
          ├──> PARKING_SLOT
          ├──< PAYMENT
          └──< VALET_REQUEST

VEHICLE
  └──< BOOKING
          └── may become linked to PARKING_SESSION

BOOKING
  └──< MPESA_TRANSACTION

PARKING_SESSION
  └──< MPESA_TRANSACTION
```

More specifically:

- One **vehicle** can have many parking sessions.
- One **parking slot** can be used by many parking sessions over time, but normally one active session at a time.
- One **parking session** can have one payment record.
- One **parking session** can have one valet request.
- One **vehicle** can have multiple bookings over time.
- A booking can become linked to one parking session when the vehicle checks in.
- M-Pesa transactions can be associated with either a booking deposit or an exit balance.

---

# 11. Database Constraints

The database uses several constraints to protect data integrity.

### Primary keys

Each major table has an integer primary key.

### Unique constraints

Examples:

```text
admins.username
vehicles.plate_number
parking_slots.slot_number
bookings.reference
mpesa_transactions.checkout_request_id
```

### Foreign keys

Foreign keys connect related entities and are enabled with:

```sql
PRAGMA foreign_keys = ON
```

### Check constraints

The database restricts certain fields to valid states.

For example:

```text
parking_slots.status:
AVAILABLE / OCCUPIED
```

and:

```text
parking_sessions.status:
ACTIVE / COMPLETED
```

---

# 12. System Architecture

NexaPark follows a simple layered structure.

```text
┌──────────────────────────────┐
│       Web Browser            │
│     HTML/CSS/JavaScript      │
└──────────────┬───────────────┘
               │ HTTP
               ▼
┌──────────────────────────────┐
│          Flask               │
│           app.py             │
│     Routes / Controllers     │
└──────────────┬───────────────┘
               │
       ┌───────┼────────┐
       ▼       ▼        ▼
   parking   pricing   auth
    logic     logic    logic
       │       │
       └───────┼─────────────┐
               ▼             ▼
        ┌────────────┐  ┌─────────────┐
        │ database.py│  │   mpesa.py  │
        └─────┬──────┘  └──────┬──────┘
              │                │
              ▼                ▼
        SQLite database    Safaricom
          parking.db       Daraja API
```

---

# 13. End-to-End Parking Workflow

## Normal parking

```text
Customer
   ↓
Enter vehicle details
   ↓
Check active session
   ↓
Check available/reserved capacity
   ↓
Find first available bay
   ↓
Create parking session
   ↓
Mark bay OCCUPIED
   ↓
Vehicle parked
```

## Normal exit

```text
Customer
   ↓
Enter plate
   ↓
Find active session
   ↓
Calculate duration
   ↓
Calculate fee
   ↓
Calculate outstanding balance
   ↓
M-Pesa STK Push
   ↓
Daraja callback
   ↓
Validate payment
   ↓
Complete session
   ↓
Mark bay AVAILABLE
   ↓
Record payment
```

## Online booking

```text
Customer
   ↓
Select arrival/departure
   ↓
Optional valet
   ↓
Calculate price
   ↓
Calculate 50% deposit
   ↓
Check overlapping capacity
   ↓
Create PENDING_PAYMENT booking
   ↓
M-Pesa STK Push
   ↓
Callback
   ↓
CONFIRMED
   ↓
Vehicle arrives
   ↓
CHECKED_IN
   ↓
Actual bay assigned
```

---

# 14. Error Handling and Validation

The system performs validation at several levels.

### User input validation

Examples:

- Empty vehicle plates are rejected.
- Plates longer than the configured maximum are rejected.
- Invalid booking dates are rejected.
- Departure must be after arrival.
- Booking start times cannot be in the past.
- Booking duration cannot exceed seven days.
- M-Pesa phone numbers are normalized and validated.
- M-Pesa payment amounts must be positive whole numbers.

### Business-rule validation

Examples:

- A vehicle cannot enter twice while it already has an active session.
- Walk-in vehicles cannot consume capacity reserved for confirmed bookings.
- A booking cannot be cancelled after it has already been checked in, cancelled or marked as a no-show.
- A payment callback must correspond to a stored M-Pesa transaction.
- The amount received must match the amount expected.

---

# 15. Security Features

The project includes several security-related mechanisms.

## Password hashing

Administrator passwords are stored as hashes using Werkzeug rather than plain text.

## Session-based authentication

Administrator access is controlled through Flask sessions.

## Temporary login lockout

Repeated failed login attempts trigger a temporary 15-minute lockout.

## Environment variables

Sensitive M-Pesa configuration and production secret values are intended to be stored in environment variables.

Examples include:

```text
MPESA_CONSUMER_KEY
MPESA_CONSUMER_SECRET
MPESA_SHORTCODE
MPESA_PASSKEY
MPESA_CALLBACK_URL
NEXAPARK_SECRET_KEY
```

## HTTPS callback requirement

The Daraja callback URL is intended to be a publicly reachable HTTPS endpoint.

---

# 16. Technologies Used

| Technology               | Purpose                                                            |
| ------------------------ | ------------------------------------------------------------------ |
| **Python 3**             | Main programming language                                          |
| **Flask**                | Web application framework                                          |
| **SQLite**               | Relational database                                                |
| **HTML**                 | Page structure                                                     |
| **CSS**                  | User-interface styling                                             |
| **JavaScript**           | Client-side interaction                                            |
| **Werkzeug**             | Password hashing and Flask security utilities                      |
| **Requests**             | HTTP communication with Daraja                                     |
| **python-dotenv**        | Loading environment variables from `.env` during local development |
| **Safaricom Daraja API** | M-Pesa STK Push payment integration                                |

---

# 17. Project File Structure

```text
modern-car-parking-system/
│
├── app.py
├── auth.py
├── database.py
├── parking.py
├── pricing.py
├── mpesa.py
├── requirements.txt
├── README.md
├── .env.example
├── .gitignore
│
├── database/
│   └── parking.db
│
├── static/
│   ├── css/
│   │   └── style.css
│   └── js/
│       └── main.js
│
└── templates/
    ├── base.html
    ├── index.html
    ├── entry.html
    ├── entry_success.html
    ├── exit.html
    ├── payment.html
    ├── payment_pending.html
    ├── exit_success.html
    ├── book.html
    ├── book_success.html
    ├── book_payment_pending.html
    ├── book_cancel.html
    ├── valet_dropoff.html
    ├── valet_dropoff_success.html
    ├── valet_pickup.html
    │
    └── admin/
        ├── base.html
        ├── login.html
        ├── dashboard.html
        ├── vehicles.html
        ├── slots.html
        ├── bookings.html
        ├── valet.html
        ├── payments.html
        ├── history.html
        └── reports.html
```

---

# 18. Summary

NexaPark is a modular parking-management application built around a Flask web server and SQLite relational database.

The system combines:

1. **Parking management** — vehicle entry, bay allocation and exit.
2. **Pricing** — duration-based parking charges and valet fees.
3. **Pre-booking** — future parking-capacity reservations.
4. **Payment processing** — M-Pesa STK Push deposits and exit balances.
5. **Valet management** — drop-off, retrieval and delivery states.
6. **Administration** — protected dashboard, monitoring, payments, history and reports.
7. **Data management** — relational storage using primary keys, foreign keys and constraints.

The design separates web routes, business logic, pricing, authentication, database access and external payment communication into dedicated modules. This makes the application easier to understand, maintain and extend.

Potential future integrations include physical barrier hardware, bay sensors, automated license-plate recognition and production hosting, but these are external to the core Flask/SQLite software implemented in the current project.

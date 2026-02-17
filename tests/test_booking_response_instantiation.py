from datetime import datetime
from core.schemas import BookingResponse


def test_booking_response_instantiation():
    data = {
        "id": "765a928d-e350-4c8f-bba5-81996075662c",
        "customer_id": "62830021-9580-423e-a3e9-24a59ec06750",
        "technician_id": None,
        "service_type_id": 3,
        "service_name": "Tyre Change",
        "technician_name": None,
        "vehicle_make": "Toyota",
        "vehicle_model": "Camry",
        "vehicle_reg_number": "ABC123",
        "problem_description": "Car won't start",
        "customer_location_lat": 49.9,
        "customer_location_lng": -8.2,
        "status": "requested",
        "status_display": "Service requested - Searching for technician",
        "estimated_price": 2000.0,
        "final_price": None,
        "payment_status": "pending",
        "requested_at": "2025-11-24T18:30:18",
        "updated_at": "2025-11-24T18:30:18"
    }

    br = BookingResponse(**data)
    print("BookingResponse instantiated:", br)


if __name__ == '__main__':
    test_booking_response_instantiation()

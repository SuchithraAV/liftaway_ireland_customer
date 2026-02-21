from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import List
from uuid import UUID
from core.database import get_db
from core.models import IssueRating, Issue, Customer, Driver, Notification
from core.schemas import IssueRatingCreate, IssueRatingResponse
from core.dependencies import get_current_customer
from core.notifications_websocket import notifications_manager
from core.utils.field_encryption import decrypt_field

router = APIRouter(prefix="/issue-ratings", tags=["Issue Ratings"])

@router.post("/", response_model=IssueRatingResponse, status_code=status.HTTP_201_CREATED)
async def create_issue_rating(
    rating_data: IssueRatingCreate,
    db: AsyncSession = Depends(get_db),
    customer: Customer = Depends(get_current_customer)
):
    """Create rating for completed issue"""
    # Verify issue exists and is completed
    issue_result = await db.execute(
        select(Issue).where(
            Issue.id == rating_data.issue_id,
            Issue.customer_id == customer.id
        )
    )
    issue = issue_result.scalar_one_or_none()
    
    if not issue:
        raise HTTPException(status_code=404, detail="Issue not found")
    
    if issue.status != "completed":
        raise HTTPException(status_code=400, detail="Issue is not completed")
    
    if not issue.assigned_driver_id:
        raise HTTPException(status_code=400, detail="No driver assigned to this issue")
    
    # Check if rating already exists
    existing_rating = await db.execute(
        select(IssueRating).where(IssueRating.issue_id == rating_data.issue_id)
    )
    if existing_rating.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Rating already exists for this issue")
    
    new_rating = IssueRating(
        issue_id=rating_data.issue_id,
        customer_id=customer.id,
        driver_id=issue.assigned_driver_id,
        rating=rating_data.rating,
        comments=rating_data.comments
    )
    
    db.add(new_rating)
    await db.commit()
    await db.refresh(new_rating)
    
    # Get driver name
    driver_result = await db.execute(
        select(Driver).where(Driver.id == issue.assigned_driver_id)
    )
    driver = driver_result.scalar_one_or_none()
    
    # Create notifications for customer and driver about the review
    try:
        # Customer notification: thank you for review
        cust_note = Notification(
            user_id=customer.id,
            user_type='customer',
            title='Review submitted',
            message=f'Thank you for reviewing {driver.full_name if driver else "the driver"}! Your feedback helps improve our service.',
            data={"issue_id": str(rating_data.issue_id), "rating": rating_data.rating}
        )
        db.add(cust_note)
        
        # Driver notification: new rating received
        driver_note = Notification(
            user_id=issue.assigned_driver_id,
            user_type='driver',
            title='New rating received',
            message=f'You received a {rating_data.rating}-star rating from {customer.full_name}.' + (f' "{rating_data.comments}"' if rating_data.comments else ''),
            data={"issue_id": str(rating_data.issue_id), "rating": rating_data.rating, "customer_name": customer.full_name}
        )
        db.add(driver_note)
        
        await db.commit()
        await db.refresh(cust_note)
        await db.refresh(driver_note)
        
        # Push live notifications via WebSocket
        try:
            await notifications_manager.send_notification(
                "customer", str(customer.id),
                {"id": str(cust_note.id), "title": cust_note.title, "message": cust_note.message, "data": cust_note.data, "is_read": False, "created_at": cust_note.created_at.isoformat() if cust_note.created_at else None}
            )
            await notifications_manager.send_notification(
                "driver", str(issue.assigned_driver_id),
                {"id": str(driver_note.id), "title": driver_note.title, "message": driver_note.message, "data": driver_note.data, "is_read": False, "created_at": driver_note.created_at.isoformat() if driver_note.created_at else None}
            )
        except Exception:
            pass
    except Exception:
        # Non-fatal: don't block the rating flow
        try:
            await db.rollback()
        except Exception:
            pass
    
    return IssueRatingResponse(
        id=new_rating.id,
        issue_id=new_rating.issue_id,
        customer_id=new_rating.customer_id,
        driver_id=new_rating.driver_id,
        rating=new_rating.rating,
        comments=new_rating.comments,
        created_at=new_rating.created_at,
        customer_name=decrypt_field(customer.full_name) if customer.full_name else None,
        driver_name=decrypt_field(driver.full_name) if driver and driver.full_name else None
    )

@router.get("/", response_model=List[IssueRatingResponse])
async def get_customer_ratings(
    customer: Customer = Depends(get_current_customer),
    db: AsyncSession = Depends(get_db)
):
    """Get all ratings given by current customer"""
    result = await db.execute(
        select(IssueRating).where(IssueRating.customer_id == customer.id).order_by(IssueRating.created_at.desc())
    )
    ratings = result.scalars().all()
    
    response_ratings = []
    for rating in ratings:
        driver_result = await db.execute(select(Driver).where(Driver.id == rating.driver_id))
        driver = driver_result.scalar_one_or_none()
        
        response_ratings.append(IssueRatingResponse(
            id=rating.id,
            issue_id=rating.issue_id,
            customer_id=rating.customer_id,
            driver_id=rating.driver_id,
            rating=rating.rating,
            comments=rating.comments,
            created_at=rating.created_at,
            customer_name=decrypt_field(customer.full_name) if customer.full_name else None,
            driver_name=decrypt_field(driver.full_name) if driver and driver.full_name else None
        ))
    
    return response_ratings

@router.get("/driver/{driver_id}", response_model=List[IssueRatingResponse])
async def get_driver_ratings(
    driver_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get all ratings for a driver"""
    result = await db.execute(
        select(IssueRating).where(IssueRating.driver_id == driver_id).order_by(IssueRating.created_at.desc())
    )
    ratings = result.scalars().all()
    
    response_ratings = []
    for rating in ratings:
        # Get customer and driver names
        customer_result = await db.execute(select(Customer).where(Customer.id == rating.customer_id))
        customer = customer_result.scalar_one_or_none()
        
        driver_result = await db.execute(select(Driver).where(Driver.id == rating.driver_id))
        driver = driver_result.scalar_one_or_none()
        
        response_ratings.append(IssueRatingResponse(
            id=rating.id,
            issue_id=rating.issue_id,
            customer_id=rating.customer_id,
            driver_id=rating.driver_id,
            rating=rating.rating,
            comments=rating.comments,
            created_at=rating.created_at,
            customer_name=decrypt_field(customer.full_name) if customer and customer.full_name else None,
            driver_name=decrypt_field(driver.full_name) if driver and driver.full_name else None
        ))
    
    return response_ratings

@router.get("/driver/{driver_id}/average")
async def get_driver_average_rating(
    driver_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    """Get average rating for a driver"""
    result = await db.execute(
        select(func.avg(IssueRating.rating), func.count(IssueRating.id))
        .where(IssueRating.driver_id == driver_id)
    )
    avg_rating, count = result.first()
    
    return {
        "driver_id": str(driver_id),
        "average_rating": float(avg_rating) if avg_rating else 0.0,
        "total_ratings": count
    }

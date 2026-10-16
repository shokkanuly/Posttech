from typing import List, Optional
from fastapi import APIRouter, Depends, Query, Request as FastAPIRequest
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.enums import RequestStatus, RequestType
from app.models.user import User
from app.schemas.request import (
    RequestCreate,
    RequestReview,
    RequestResponse,
    RequestDetailResponse,
)
from app.services.auth_service import get_current_user
from app.services.request_service import request_service

router = APIRouter(prefix="/requests", tags=["Employee Requests"])


@router.get("", response_model=List[RequestResponse])
def list_requests(
    status: Optional[RequestStatus] = Query(None, description="Filter by status (Pending, Approved, Rejected)"),
    type: Optional[RequestType] = Query(None, description="Filter by type (Vacation, Advance payment)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    requests = request_service.get_user_requests(db, current_user, status_filter=status, type_filter=type)
    return [request_service.to_response(r) for r in requests]


@router.post("", response_model=RequestResponse, status_code=201)
def create_request(
    payload: RequestCreate,
    request: FastAPIRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    ip_addr = request.client.host if request.client else None
    new_req = request_service.create_request(db, current_user, payload, ip_address=ip_addr)
    return request_service.to_response(new_req)


@router.get("/{request_id}", response_model=RequestDetailResponse)
def get_request_detail(
    request_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    req = request_service.get_request_by_id(db, request_id, current_user)
    return request_service.to_detail_response(req)


@router.post("/{request_id}/approve", response_model=RequestDetailResponse)
def approve_request(
    request_id: int,
    payload: Optional[RequestReview] = None,
    request: FastAPIRequest = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    comment = payload.comment if payload else None
    ip_addr = request.client.host if (request and request.client) else None
    req = request_service.review_request(
        db=db,
        request_id=request_id,
        reviewer=current_user,
        action="approve",
        comment=comment,
        ip_address=ip_addr,
    )
    return request_service.to_detail_response(req)


@router.post("/{request_id}/reject", response_model=RequestDetailResponse)
def reject_request(
    request_id: int,
    payload: Optional[RequestReview] = None,
    request: FastAPIRequest = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    comment = payload.comment if payload else None
    ip_addr = request.client.host if (request and request.client) else None
    req = request_service.review_request(
        db=db,
        request_id=request_id,
        reviewer=current_user,
        action="reject",
        comment=comment,
        ip_address=ip_addr,
    )
    return request_service.to_detail_response(req)

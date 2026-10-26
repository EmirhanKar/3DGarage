# app/api/routers/community_router.py — YENİ DOSYA

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc
from sqlalchemy.orm import selectinload
from typing import List

from app.database.db import get_session
from app.database.models import Scans, User, Like, Comment, CommentLike
from app.database.models.processed_3D import Processed3D
from app.database.models.processed_2D import Processed2D
from app.api import get_current_user
from app.database.schemas.community_schemas import (
    CommentCreate, CommentResponse, FeedItemResponse
)

router = APIRouter(prefix="/community")


# ─────────────────────────────────────────
# KEŞFET FEED
# ─────────────────────────────────────────

@router.get("/feed", response_model=List[FeedItemResponse], tags=["Community"])
async def get_feed(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Sadece toplulukla paylaşılmış araçları keşfet sayfası için listeler."""

    # Sadece is_shared=True olan completed scan'leri getir
    query = (
        select(Scans)
        .where(Scans.status == "completed")
        .where(Scans.is_shared == True)
        .options(
            selectinload(Scans.processed_3d),
            selectinload(Scans.processed_2d),
        )
        .order_by(Scans.created_at.desc())
    )
    result = await db.execute(query)
    scans = result.scalars().all()

    feed = []
    for scan in scans:
        # Beğeni sayısı
        like_count_result = await db.execute(
            select(func.count()).where(Like.scan_id == scan.scan_id)
        )
        like_count = like_count_result.scalar()

        # Yorum sayısı
        comment_count_result = await db.execute(
            select(func.count()).where(Comment.scan_id == scan.scan_id)
        )
        comment_count = comment_count_result.scalar()

        # Giriş yapan kullanıcı beğenmiş mi?
        liked_result = await db.execute(
            select(Like).where(
                Like.scan_id == scan.scan_id,
                Like.user_id == current_user.user_id
            )
        )
        is_liked = liked_result.scalar_one_or_none() is not None

        # Araç sahibi
        owner_result = await db.execute(select(User).where(User.user_id == scan.user_id))
        owner = owner_result.scalar_one_or_none()

        # Thumbnail
        thumbnail_url = None
        if scan.processed_3d:
            thumbnail_url = scan.processed_3d.thumbnail_url
        elif scan.processed_2d:
            thumbnail_url = scan.processed_2d.thumbnail_url

        feed.append(FeedItemResponse(
            scan_id=scan.scan_id,
            car_name=scan.car_name,
            thumbnail_url=thumbnail_url,
            like_count=like_count,
            comment_count=comment_count,
            is_liked=is_liked,
            owner_name=f"{owner.name} {owner.surname}" if owner else "Bilinmiyor"
        ))

    return feed


@router.get("/explore/top", response_model=List[FeedItemResponse], tags=["Community"])
async def get_top_explore(
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """En çok beğenilen 5 topluluk aracını getirir."""
    # Sadece is_shared=True olan completed scan'leri getir, beğeni sayısına göre sırala
    query = (
        select(Scans, func.count(Like.like_id).label("like_count"))
        .join(Like, Like.scan_id == Scans.scan_id, isouter=True)
        .where(Scans.status == "completed")
        .where(Scans.is_shared == True)
        .group_by(Scans.scan_id)
        .order_by(desc("like_count"), Scans.created_at.desc())
        .limit(5)
        .options(
            selectinload(Scans.processed_3d),
            selectinload(Scans.processed_2d),
        )
    )
    result = await db.execute(query)
    scans_with_likes = result.all()

    feed = []
    for scan, like_count in scans_with_likes:
        # Yorum sayısı
        comment_count_result = await db.execute(
            select(func.count()).where(Comment.scan_id == scan.scan_id)
        )
        comment_count = comment_count_result.scalar()

        # Giriş yapan kullanıcı beğenmiş mi?
        liked_result = await db.execute(
            select(Like).where(
                Like.scan_id == scan.scan_id,
                Like.user_id == current_user.user_id
            )
        )
        is_liked = liked_result.scalar_one_or_none() is not None

        # Araç sahibi
        owner_result = await db.execute(select(User).where(User.user_id == scan.user_id))
        owner = owner_result.scalar_one_or_none()

        # Thumbnail
        thumbnail_url = None
        if scan.processed_3d:
            thumbnail_url = scan.processed_3d.thumbnail_url
        elif scan.processed_2d:
            thumbnail_url = scan.processed_2d.thumbnail_url

        feed.append(FeedItemResponse(
            scan_id=scan.scan_id,
            car_name=scan.car_name,
            thumbnail_url=thumbnail_url,
            like_count=like_count,
            comment_count=comment_count,
            is_liked=is_liked,
            owner_name=f"{owner.name} {owner.surname}" if owner else "Bilinmiyor"
        ))

    return feed


# ─────────────────────────────────────────
# BEĞENİ
# ─────────────────────────────────────────

@router.post("/{scan_id}/like", status_code=status.HTTP_200_OK, tags=["Community"])
async def toggle_like(
    scan_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Beğen / beğeniyi geri al. Her çağrıda toggle yapar."""

    # Scan var mı?
    scan = await db.get(Scans, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Araç bulunamadı.")

    # Daha önce beğenmiş mi?
    result = await db.execute(
        select(Like).where(Like.scan_id == scan_id, Like.user_id == current_user.user_id)
    )
    existing_like = result.scalar_one_or_none()

    if existing_like:
        # Beğeniyi geri al
        await db.delete(existing_like)
        await db.commit()
        return {"liked": False, "message": "Beğeni kaldırıldı."}
    else:
        # Beğen
        new_like = Like(user_id=current_user.user_id, scan_id=scan_id)
        db.add(new_like)
        await db.commit()
        return {"liked": True, "message": "Beğenildi."}


# ─────────────────────────────────────────
# YORUMLAR
# ─────────────────────────────────────────

@router.get("/{scan_id}/comments", response_model=List[CommentResponse], tags=["Community"])
async def get_comments(
    scan_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Bir aracın yorumlarını listeler."""
    result = await db.execute(
        select(Comment)
        .where(Comment.scan_id == scan_id)
        .order_by(Comment.created_at.desc())
    )
    comments = result.scalars().all()
    
    response = []
    for c in comments:
        user_res = await db.execute(select(User).where(User.user_id == c.user_id))
        user_obj = user_res.scalar_one_or_none()
        u_name = f"{user_obj.name} {user_obj.surname}" if user_obj else "Kullanıcı"
        
        like_count_res = await db.execute(
            select(func.count()).where(CommentLike.comment_id == c.comment_id)
        )
        like_count = like_count_res.scalar()
        
        is_liked_res = await db.execute(
            select(CommentLike).where(
                CommentLike.comment_id == c.comment_id,
                CommentLike.user_id == current_user.user_id
            )
        )
        is_liked = is_liked_res.scalar_one_or_none() is not None
        
        response.append(CommentResponse(
            comment_id=c.comment_id,
            scan_id=c.scan_id,
            user_id=c.user_id,
            content=c.content,
            created_at=c.created_at,
            user_name=u_name,
            like_count=like_count,
            is_liked=is_liked
        ))
    return response


@router.post("/{scan_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED, tags=["Community"])
async def add_comment(
    scan_id: int,
    comment_in: CommentCreate,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Bir araca yorum ekler."""
    scan = await db.get(Scans, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Araç bulunamadı.")

    new_comment = Comment(
        user_id=current_user.user_id,
        scan_id=scan_id,
        content=comment_in.content
    )
    db.add(new_comment)
    await db.commit()
    await db.refresh(new_comment)
    
    u_name = f"{current_user.name} {current_user.surname}"
    return CommentResponse(
        comment_id=new_comment.comment_id,
        scan_id=new_comment.scan_id,
        user_id=new_comment.user_id,
        content=new_comment.content,
        created_at=new_comment.created_at,
        user_name=u_name,
        like_count=0,
        is_liked=False
    )


@router.post("/comments/{comment_id}/like", status_code=status.HTTP_200_OK, tags=["Community"])
async def toggle_comment_like(
    comment_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Yorumu beğen / beğeniyi geri al. Her çağrıda toggle yapar."""
    comment = await db.get(Comment, comment_id)
    if not comment:
        raise HTTPException(status_code=404, detail="Yorum bulunamadı.")

    result = await db.execute(
        select(CommentLike).where(
            CommentLike.comment_id == comment_id,
            CommentLike.user_id == current_user.user_id
        )
    )
    existing_like = result.scalar_one_or_none()

    if existing_like:
        await db.delete(existing_like)
        await db.commit()
        return {"liked": False, "message": "Yorum beğenisi kaldırıldı."}
    else:
        new_like = CommentLike(user_id=current_user.user_id, comment_id=comment_id)
        db.add(new_like)
        await db.commit()
        return {"liked": True, "message": "Yorum beğenildi."}



@router.delete("/comments/{comment_id}", status_code=status.HTTP_200_OK, tags=["Community"])
async def delete_comment(
    comment_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Kendi yorumunu siler."""
    result = await db.execute(select(Comment).where(Comment.comment_id == comment_id))
    comment = result.scalar_one_or_none()

    if not comment:
        raise HTTPException(status_code=404, detail="Yorum bulunamadı.")

    if comment.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Bu yorumu silme yetkiniz yok.")

    await db.delete(comment)
    await db.commit()
    return {"message": "Yorum silindi."}


# ─────────────────────────────────────────
# TOPLULUKLA PAYLAŞMA
# ─────────────────────────────────────────

@router.post("/{scan_id}/share", status_code=status.HTTP_200_OK, tags=["Community"])
async def share_to_community(
    scan_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Aracı toplulukla paylaşır (keşfette görünür hale getirir)."""
    scan = await db.get(Scans, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Araç bulunamadı.")
    if scan.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Bu araca erişim yetkiniz yok.")
    if scan.status != "completed":
        raise HTTPException(status_code=400, detail="Sadece tamamlanmış araçlar paylaşılabilir.")

    scan.is_shared = True
    await db.commit()
    return {"message": "Araç toplulukla paylaşıldı!", "is_shared": True}


@router.post("/{scan_id}/unshare", status_code=status.HTTP_200_OK, tags=["Community"])
async def unshare_from_community(
    scan_id: int,
    db: AsyncSession = Depends(get_session),
    current_user: User = Depends(get_current_user)
):
    """Aracı keşfetten kaldırır."""
    scan = await db.get(Scans, scan_id)
    if not scan:
        raise HTTPException(status_code=404, detail="Araç bulunamadı.")
    if scan.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Bu araca erişim yetkiniz yok.")

    scan.is_shared = False
    await db.commit()
    return {"message": "Araç keşfetten kaldırıldı.", "is_shared": False}
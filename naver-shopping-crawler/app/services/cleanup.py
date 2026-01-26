from datetime import datetime, timedelta
from sqlalchemy import delete
from app.database import async_session
from app.models import RankingHistory


async def cleanup_old_rankings(days: int = 30):
    """
    오래된 순위 기록 삭제

    Args:
        days: 보관 기간 (기본 30일)
    """
    cutoff_date = datetime.utcnow() - timedelta(days=days)

    async with async_session() as db:
        result = await db.execute(
            delete(RankingHistory).where(
                RankingHistory.recorded_at < cutoff_date
            )
        )
        await db.commit()

        deleted_count = result.rowcount
        print(f"[Cleanup] {deleted_count}개의 오래된 순위 기록 삭제됨 ({days}일 이전)")

        return deleted_count

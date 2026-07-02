from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.services.lock_service import try_advisory_lock


async def test_second_session_cannot_acquire_held_lock(db_engine):
    session_local = async_sessionmaker(db_engine, expire_on_commit=False)

    async with session_local() as session_a, session_local() as session_b:
        async with try_advisory_lock(session_a, "test-lock") as acquired_a:
            assert acquired_a is True
            async with try_advisory_lock(session_b, "test-lock") as acquired_b:
                assert acquired_b is False


async def test_lock_is_released_and_reacquirable(db_engine):
    session_local = async_sessionmaker(db_engine, expire_on_commit=False)

    async with session_local() as session:
        async with try_advisory_lock(session, "test-lock-2") as acquired:
            assert acquired is True
        # Released on exit -- a fresh attempt on the same session should succeed again.
        async with try_advisory_lock(session, "test-lock-2") as acquired_again:
            assert acquired_again is True


async def test_different_lock_names_dont_conflict(db_engine):
    session_local = async_sessionmaker(db_engine, expire_on_commit=False)

    async with session_local() as session_a, session_local() as session_b:
        async with try_advisory_lock(session_a, "lock-alpha") as a:
            async with try_advisory_lock(session_b, "lock-beta") as b:
                assert a is True
                assert b is True

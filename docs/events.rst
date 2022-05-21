Using SQLAlchemy events with Asphalt
====================================

While asphalt-sqlalchemy does not provide support for Asphalt style events at this time,
you can still listen to the native SQLAlchemy events.

Events with synchronous engines/sessions
----------------------------------------

In order to add a listener that applies to every ORM session created in the future, you
can add your listener in the :class:`~sqlalchemy.orm.session.sessionmaker` which is
published by the SQLAlchemy component as a resource::

    from asphalt.core import inject, resource
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import event


    def precommit_hook(session):
        ...  # execute the pre-commit logic


    @inject
    async def handler(session_factory: sessionmaker = resource()):
        event.listen(session_factory, 'before_commit', precommit_hook)

Events with asynchronous engines/sessions
-----------------------------------------

SQLAlchemy doesn't support asynchronous events yet, and sessionmakers producing async
session cannot currently used as a target for event listeners. As a workaround, you can
register an event listener on the :class:`~sqlalchemy.orm.Session` class and then check
in the listener itself if the ``session`` argument matches the async session's
``sync_session`` attribute in the current context::

    from asphalt.core import NoCurrentContext, get_resource, inject, resource
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import event


    def precommit_hook(session):
        try:
            async_session = get_resource(AsyncSession)
        except NoCurrentContext:
            return

        if async_session and session is async_session.sync_session:
            ...  # execute the pre-commit logic


    @inject
    async def handler(session_factory: sessionmaker = resource()):
        event.listen(session_factory, 'before_commit', precommit_hook)


For more information on asyncio support and events, see the `SQLAlchemy documentation`_.

.. _SQLAlchemy documentation: https://docs.sqlalchemy.org/en/14/orm/extensions/asyncio.html#using-events-with-the-asyncio-extension

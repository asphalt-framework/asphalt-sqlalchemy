Using SQLAlchemy events with Asphalt
====================================

While asphalt-sqlalchemy does not provide support for Asphalt style events at this time, you can
still listen to the native SQLAlchemy events. Limited support is provided for interacting with the
context from **session events**. Every ORM session object will have its associated session object
stored in its ``info`` dictionary (``ctx.sql.info['ctx'] is ctx``).

In order to add a listener that applies to every ORM session created in the future, you can add
your listener in the :class:`~sqlalchemy.orm.session.sessionmaker` which is published by the
SQLAlchemy component as a resource::

    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import event


    def precommit_hook(session):
        ctx = session.info['ctx']
        # do something with the context


    async def handler(ctx):
        session_factory = ctx.require_resource(sessionmaker)
        event.listen(session_factory, 'before_commit', precommit_hook)


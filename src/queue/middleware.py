from dramatiq.middleware import Middleware

from src.queue.store import task_store


class TaskTrackingMiddleware(Middleware):
    """Keep the Redis task record in step with the Dramatiq message lifecycle."""

    def after_enqueue(self, broker, message, delay):
        task_store.create(message.message_id, message.actor_name, message.queue_name)

    def before_process_message(self, broker, message):
        task_store.mark_running(message.message_id)

    def after_process_message(self, broker, message, *, result=None, exception=None):
        if exception is None:
            task_store.mark_success(message.message_id)
        else:
            task_store.mark_failure(message.message_id, str(exception))

    def after_skip_message(self, broker, message):
        # Failed attempt with retries left: the message is re-enqueued.
        task_store.mark_queued(message.message_id)

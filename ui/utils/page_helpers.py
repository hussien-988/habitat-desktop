from services.translation_manager import tr


def show_error_state(empty_state, stack, error_msg: str, retry_fn) -> None:
    """Display connection error state with retry button."""
    empty_state.configure(
        title=tr("error.connection_failed_title"),
        description=error_msg or tr("error.connection_failed_description"),
    )
    empty_state.set_action(tr("button.retry"), retry_fn)
    stack.setCurrentIndex(1)

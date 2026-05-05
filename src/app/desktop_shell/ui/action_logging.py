from __future__ import annotations

import logging
from collections.abc import Callable

from PySide6.QtWidgets import (
    QComboBox,
    QLineEdit,
    QPushButton,
    QTableWidget,
    QWidget,
)

logger = logging.getLogger("app.ui.actions")

_INSTALLED_PROPERTY = "_ui_action_logger_installed"


def log_ui_action(screen: str, action: str, **details: object) -> None:
    detail_text = " ".join(f"{key}={value!r}" for key, value in details.items())
    message = f"{screen}: {action}"
    if detail_text:
        message = f"{message} {detail_text}"
    logger.info(message)


def install_action_logging(
    root: QWidget,
    *,
    screen: str,
    context: Callable[[], dict[str, object]] | None = None,
) -> None:
    _install_for_widget(root, screen=screen, context=context)
    for widget in root.findChildren(QWidget):
        _install_for_widget(widget, screen=screen, context=context)


def attach_action_logging(
    widget: QWidget,
    *,
    screen: str,
    context: Callable[[], dict[str, object]] | None = None,
) -> None:
    _install_for_widget(widget, screen=screen, context=context)


def _install_for_widget(
    widget: QWidget,
    *,
    screen: str,
    context: Callable[[], dict[str, object]] | None,
) -> None:
    if widget.property(_INSTALLED_PROPERTY):
        return

    if isinstance(widget, QPushButton):
        widget.clicked.connect(
            lambda _checked=False, source=widget: _log_widget_action(
                screen,
                "button_clicked",
                source,
                context,
                text=source.text(),
            )
        )
    elif isinstance(widget, QComboBox):
        widget.currentTextChanged.connect(
            lambda value, source=widget: _log_widget_action(
                screen,
                "selection_changed",
                source,
                context,
                value=value,
            )
        )
    elif isinstance(widget, QLineEdit):
        widget.returnPressed.connect(
            lambda source=widget: _log_widget_action(
                screen,
                "input_submitted",
                source,
                context,
            )
        )
        widget.editingFinished.connect(
            lambda source=widget: _log_widget_action(
                screen,
                "input_finished",
                source,
                context,
            )
        )
    elif isinstance(widget, QTableWidget):
        widget.cellClicked.connect(
            lambda row, column, source=widget: _log_widget_action(
                screen,
                "table_cell_clicked",
                source,
                context,
                row=row,
                column=column,
            )
        )
        widget.cellDoubleClicked.connect(
            lambda row, column, source=widget: _log_widget_action(
                screen,
                "table_cell_double_clicked",
                source,
                context,
                row=row,
                column=column,
            )
        )
    else:
        return

    widget.setProperty(_INSTALLED_PROPERTY, True)


def _log_widget_action(
    screen: str,
    action: str,
    widget: QWidget,
    context: Callable[[], dict[str, object]] | None,
    **details: object,
) -> None:
    payload: dict[str, object] = {
        "widget": _widget_label(widget),
        **details,
    }
    if context is not None:
        payload.update(context())
    log_ui_action(screen, action, **payload)


def _widget_label(widget: QWidget) -> str:
    object_name = widget.objectName().strip()
    if object_name:
        return object_name
    if isinstance(widget, QPushButton):
        return widget.text().strip() or widget.__class__.__name__
    return widget.__class__.__name__

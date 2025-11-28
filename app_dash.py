import os
import json
from datetime import datetime

import dash
from dash import dcc, html
import dash_bootstrap_components as dbc

from chat_db import init_db, list_chats, create_chat
from callbacks.chat_callbacks import register_chat_callbacks

# ---------- App & Theme ----------
external_stylesheets = [dbc.themes.CYBORG]
app = dash.Dash(
    __name__,
    external_stylesheets=external_stylesheets,
    suppress_callback_exceptions=True,
)
server = app.server

# ---------- Styles ----------
CHAT_BUBBLE_CSS = {
    "assistant": {
        "background": "rgba(255,255,255,0.06)",
        "border": "1px solid rgba(255,255,255,0.08)",
        "padding": "10px 14px",
        "borderRadius": "16px",
        "maxWidth": "80%",
        "backdropFilter": "blur(10px)",
        "boxShadow": "0 8px 20px rgba(0,0,0,0.25)",
        "marginBottom": "10px",
    },
    "user": {
        "background": "linear-gradient(135deg, rgba(0,150,255,0.25), rgba(100,50,255,0.25))",
        "border": "1px solid rgba(255,255,255,0.15)",
        "padding": "10px 14px",
        "borderRadius": "16px",
        "maxWidth": "80%",
        "backdropFilter": "blur(10px)",
        "boxShadow": "0 8px 20px rgba(0,0,0,0.25)",
        "marginBottom": "10px",
    },
}


def chat_item(chat, active_id):
    """One row in the chat history list (left sidebar)."""
    cid = chat.get("id")
    cid_str = str(cid)
    is_active = str(active_id) == cid_str

    return dbc.ListGroupItem(
        [
            html.Div(
                [
                    html.Div(
                        chat.get("title", "Chat"),
                        className="fw-semibold text-truncate",
                        style={"maxWidth": "180px"},
                    ),
                    dbc.DropdownMenu(
                        label="⋮",
                        size="sm",
                        color="secondary",
                        class_name="ms-auto",
                        toggleClassName="btn-sm",
                        children=[
                            dbc.DropdownMenuItem(
                                "Rename",
                                id={"type": "chat-action", "key": f"{cid_str}|rename"},
                            ),
                            dbc.DropdownMenuItem(
                                "Delete",
                                id={"type": "chat-action", "key": f"{cid_str}|delete"},
                            ),
                        ],
                        direction="down",
                    ),
                ],
                className="d-flex align-items-center justify-content-between",
            ),
        ],
        id={"type": "chat-select", "chat_id": cid_str},
        action=True,
        active=is_active,
        class_name="rounded-3",
        style={"background": "rgba(255,255,255,0.05)" if is_active else "transparent"},
    )


def messages_view(messages):
    """Render list of messages to chat bubbles."""
    ui = []
    for m in messages:
        role = m["role"]
        is_user = role == "user"
        bubble_style = CHAT_BUBBLE_CSS["user" if is_user else "assistant"]
        row_cls = "d-flex justify-content-end" if is_user else "d-flex justify-content-start"

        content_children = [html.Div(m["content"])]
        meta = m.get("meta") or {}

        if meta.get("image_preview"):
            content_children.insert(
                0,
                html.Img(
                    src=meta["image_preview"],
                    style={"maxWidth": "240px", "borderRadius": "12px", "marginBottom": "8px"},
                ),
            )

        if meta.get("tags"):
            content_children.append(
                html.Div(
                    [html.Span(f"#{t}", className="badge bg-secondary me-1") for t in meta["tags"]],
                    className="mt-2",
                )
            )

        ui.append(
            html.Div(
                [html.Div(content_children, style=bubble_style)],
                className=row_cls,
            )
        )
    return ui


# ---------- Layout ----------
app.layout = dbc.Container(
    fluid=True,
    children=[
        dcc.Store(id="active-chat-id"),
        dcc.Store(id="rename-target-id"),
        dcc.Store(id="upload-image-b64"),
        dcc.Interval(id="tick", interval=500, n_intervals=0, max_intervals=1),

        dbc.Row(
            [
                # Sidebar
                dbc.Col(
                    width=3,
                    children=[
                        html.Div(
                            [
                                html.Div(
                                    [
                                        html.H4("Chats", className="mb-0"),
                                        dbc.Button(
                                            "➕ New chat",
                                            id="new-chat",
                                            size="sm",
                                            color="primary",
                                            className="ms-auto",
                                        ),
                                    ],
                                    className="d-flex align-items-center justify-content-between mb-3",
                                ),
                                dbc.ListGroup(
                                    id="chat-list",
                                    flush=True,
                                    class_name="rounded-3",
                                ),
                            ],
                            style={
                                "height": "95vh",
                                "overflowY": "auto",
                                "padding": "16px",
                                "background": "rgba(255,255,255,0.03)",
                                "borderRight": "1px solid rgba(255,255,255,0.08)",
                            },
                        )
                    ],
                    class_name="px-0",
                ),

                # Main area
                dbc.Col(
                    width=9,
                    children=[
                        html.Div(
                            [
                                html.Div(
                                    [html.H4(id="chat-title", className="mb-0")],
                                    className="d-flex align-items-center justify-content-between mb-2",
                                ),
                                dbc.Card(
                                    [
                                        dbc.CardBody(
                                            dcc.Loading(
                                                id="loading-chat",
                                                type="circle",
                                                children=html.Div(
                                                    id="chat-messages",
                                                    style={
                                                        "minHeight": "65vh",
                                                        "overflowY": "auto",
                                                        "padding": "8px",
                                                    },
                                                ),
                                            )
                                        )
                                    ],
                                    class_name="mb-3 rounded-4",
                                    style={
                                        "background": "rgba(255,255,255,0.03)",
                                        "border": "1px solid rgba(255,255,255,0.08)",
                                    },
                                ),
                                # Composer
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            [
                                                dbc.Input(
                                                    id="user-input",
                                                    placeholder="Type your message...",
                                                    type="text",
                                                )
                                            ],
                                            width=9,
                                        ),
                                        dbc.Col(
                                            [
                                                dbc.Button(
                                                    "Send",
                                                    id="send-btn",
                                                    color="success",
                                                    className="w-100",
                                                )
                                            ],
                                            width=3,
                                        ),
                                    ],
                                    class_name="g-2",
                                ),
                                # Image upload row
                                html.Div(className="mt-3"),
                                dbc.Row(
                                    [
                                        dbc.Col(
                                            [
                                                dcc.Upload(
                                                    id="image-upload",
                                                    children=html.Div(
                                                        ["Drag & drop or ", html.A("select an image")]
                                                    ),
                                                    multiple=False,
                                                    style={
                                                        "width": "100%",
                                                        "height": "70px",
                                                        "lineHeight": "70px",
                                                        "borderWidth": "1px",
                                                        "borderStyle": "dashed",
                                                        "borderRadius": "10px",
                                                        "textAlign": "center",
                                                        "background": "rgba(255,255,255,0.02)",
                                                    },
                                                )
                                            ],
                                            width=9,
                                        ),
                                        dbc.Col(
                                            [
                                                dbc.Button(
                                                    "Generate Caption",
                                                    id="caption-btn",
                                                    color="info",
                                                    className="w-100",
                                                )
                                            ],
                                            width=3,
                                        ),
                                    ],
                                    class_name="g-2",
                                    align="center",
                                ),
                            ],
                            style={"height": "95vh", "padding": "16px"},
                        )
                    ],
                    class_name="px-0",
                ),
            ]
        ),

        # Rename modal
        dbc.Modal(
            [
                dbc.ModalHeader("Rename chat"),
                dbc.ModalBody(dbc.Input(id="rename-input", placeholder="Enter new title...")),
                dbc.ModalFooter(
                    [
                        dbc.Button("Cancel", id="rename-cancel", color="secondary"),
                        dbc.Button("Save", id="rename-save", color="primary"),
                    ]
                ),
            ],
            id="rename-modal",
            is_open=False,
        ),

        # Delete modal
        dbc.Modal(
            [
                dbc.ModalHeader("Delete chat"),
                dbc.ModalBody("Are you sure you want to delete this chat?"),
                dbc.ModalFooter(
                    [
                        dbc.Button("Cancel", id="delete-cancel", color="secondary"),
                        dbc.Button("Delete", id="delete-confirm", color="danger"),
                    ]
                ),
            ],
            id="delete-modal",
            is_open=False,
        ),
    ],
)

# ---------- Init DB & default chat ----------
init_db()
existing = list_chats()
if not existing:
    first_id = create_chat("New chat")
else:
    first_id = existing[0]["id"]

# ---------- Register callbacks ----------
register_chat_callbacks(app, chat_item, messages_view)


if __name__ == "__main__":
    # Command line:  python app_dash.py
    app.run(host="0.0.0.0", port=8050, debug=False)

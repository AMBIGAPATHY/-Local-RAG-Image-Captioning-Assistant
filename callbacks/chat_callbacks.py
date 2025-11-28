# callbacks/chat_callbacks.py

from datetime import datetime

from dash import Input, Output, State, ALL, ctx, no_update
import dash

from chat_db import (
    list_chats,
    create_chat,
    rename_chat,
    delete_chat,
    add_message,
    get_messages,
)
from rag_backend import answer_text, caption_image


def register_chat_callbacks(app: dash.Dash, chat_item, messages_view):
    """
    Register all Dash callbacks for the chat UI.
    `chat_item` and `messages_view` are helper functions passed from app_dash.py
    """

    # ---------- Populate sidebar and active chat on load ----------
    @app.callback(
        Output("chat-list", "children"),
        Output("active-chat-id", "data"),
        Input("tick", "n_intervals"),
        prevent_initial_call=False,
    )
    def initial_fill(_):
        try:
            chats = list_chats()
            if not chats:
                active = create_chat("New chat")
                chats = list_chats()
            else:
                active = chats[0]["id"]

            items = [chat_item(c, active) for c in chats]
            return items, active
        except Exception as e:
            print(f"[ERROR] initial_fill: {e}", flush=True)
            return no_update, no_update

    # ---------- New chat ----------
    @app.callback(
        Output("chat-list", "children", allow_duplicate=True),
        Output("active-chat-id", "data", allow_duplicate=True),
        Input("new-chat", "n_clicks"),
        prevent_initial_call=True,
    )
    def make_new_chat(n):
        try:
            if not n:
                return no_update, no_update
            cid = create_chat("New chat")
            chats = list_chats()
            return [chat_item(c, cid) for c in chats], cid
        except Exception as e:
            print(f"[ERROR] make_new_chat: {e}", flush=True)
            return no_update, no_update

    # ---------- Select chat from sidebar ----------
    @app.callback(
        Output("active-chat-id", "data", allow_duplicate=True),
        Input({"type": "chat-select", "chat_id": ALL}, "n_clicks"),
        State("active-chat-id", "data"),
        prevent_initial_call=True,
    )
    def choose_chat(n_clicks_list, current):
        try:
            if not n_clicks_list:
                return no_update
            triggered = ctx.triggered_id
            if isinstance(triggered, dict) and "chat_id" in triggered:
                chat_id_str = triggered["chat_id"]
                try:
                    return int(chat_id_str)
                except Exception:
                    return chat_id_str
            return no_update
        except Exception as e:
            print(f"[ERROR] choose_chat: {e}", flush=True)
            return no_update

    # ---------- Render chat area (title + messages) ----------
    @app.callback(
        Output("chat-title", "children"),
        Output("chat-messages", "children"),
        Input("active-chat-id", "data"),
        prevent_initial_call=True,
    )
    def render_chat(active_id):
        try:
            if not active_id:
                return "New chat", []
            chats = list_chats()
            title = next((c["title"] for c in chats if str(c["id"]) == str(active_id)), "Chat")
            messages = get_messages(active_id)
            return title, messages_view(messages)
        except Exception as e:
            print(f"[ERROR] render_chat: {e}", flush=True)
            return no_update, no_update

    # ---------- Send message (click or Enter) ----------
    @app.callback(
        Output("chat-messages", "children", allow_duplicate=True),
        Output("chat-title", "children", allow_duplicate=True),
        Output("chat-list", "children", allow_duplicate=True),
        Output("user-input", "value", allow_duplicate=True),
        Input("send-btn", "n_clicks"),
        Input("user-input", "n_submit"),
        State("user-input", "value"),
        State("active-chat-id", "data"),
        prevent_initial_call=True,
    )
    def on_send(clicks, submits, text, chat_id):
        try:
            if not text or not chat_id:
                return no_update, no_update, no_update, no_update

            # add user msg
            add_message(chat_id, "user", text, meta=None)

            # auto-title if default
            chats = list_chats()
            title = next((c["title"] for c in chats if str(c["id"]) == str(chat_id)), "New chat")
            if title == "New chat":
                new_title = text.strip()[:40]
                if new_title:
                    rename_chat(chat_id, new_title)

            # assistant answer via RAG + Gemini
            reply = answer_text(text)
            add_message(chat_id, "assistant", reply, meta=None)

            # refresh
            chats = list_chats()
            title = next((c["title"] for c in chats if str(c["id"]) == str(chat_id)), "Chat")
            messages = get_messages(chat_id)
            return (
                messages_view(messages),
                title,
                [chat_item(c, chat_id) for c in chats],
                "",  # clear input
            )
        except Exception as e:
            print(f"[ERROR] on_send: {e}", flush=True)
            # don't crash UI; keep previous content, don't clear input
            return no_update, no_update, no_update, no_update

    # ---------- Three-dot menu: rename / delete (open modals) ----------
    @app.callback(
        Output("rename-modal", "is_open", allow_duplicate=True),
        Output("rename-target-id", "data", allow_duplicate=True),
        Output("delete-modal", "is_open", allow_duplicate=True),
        Input({"type": "chat-action", "key": ALL}, "n_clicks"),
        prevent_initial_call=True,
    )
    def open_action_modals(n_list):
        try:
            # ignore initial state where all clicks are zero
            if not n_list or all((n or 0) == 0 for n in n_list):
                return no_update, no_update, no_update

            trig = ctx.triggered_id
            if isinstance(trig, dict):
                key = trig.get("key")
                if not key:
                    return no_update, no_update, no_update
                try:
                    chat_id_str, action = key.split("|", 1)
                except ValueError:
                    return no_update, no_update, no_update

                try:
                    chat_id = int(chat_id_str)
                except Exception:
                    chat_id = chat_id_str

                if action == "rename":
                    return True, chat_id, False
                elif action == "delete":
                    return False, chat_id, True

            return no_update, no_update, no_update
        except Exception as e:
            print(f"[ERROR] open_action_modals: {e}", flush=True)
            return no_update, no_update, no_update

    # ---------- Handle rename modal ----------
    @app.callback(
        Output("rename-modal", "is_open", allow_duplicate=True),
        Output("chat-list", "children", allow_duplicate=True),
        Output("chat-title", "children", allow_duplicate=True),
        Input("rename-save", "n_clicks"),
        Input("rename-cancel", "n_clicks"),
        State("rename-target-id", "data"),
        State("rename-input", "value"),
        State("active-chat-id", "data"),
        prevent_initial_call=True,
    )
    def handle_rename(save, cancel, chat_id, new_title, active_id):
        try:
            if ctx.triggered_id == "rename-cancel":
                return False, no_update, no_update
            if not save or not chat_id or not new_title:
                return no_update, no_update, no_update

            rename_chat(chat_id, new_title.strip())
            chats = list_chats()
            title = next((c["title"] for c in chats if str(c["id"]) == str(active_id)), "Chat")
            return False, [chat_item(c, active_id) for c in chats], title
        except Exception as e:
            print(f"[ERROR] handle_rename: {e}", flush=True)
            return no_update, no_update, no_update

    # ---------- Handle delete modal ----------
    @app.callback(
        Output("delete-modal", "is_open", allow_duplicate=True),
        Output("chat-list", "children", allow_duplicate=True),
        Output("active-chat-id", "data", allow_duplicate=True),
        Input("delete-confirm", "n_clicks"),
        Input("delete-cancel", "n_clicks"),
        State("rename-target-id", "data"),
        prevent_initial_call=True,
    )
    def handle_delete(confirm, cancel, chat_id):
        try:
            if ctx.triggered_id == "delete-cancel":
                return False, no_update, no_update
            if not confirm or not chat_id:
                return no_update, no_update, no_update

            delete_chat(chat_id)
            chats = list_chats()
            new_active = chats[0]["id"] if chats else create_chat("New chat")
            return False, [chat_item(c, new_active) for c in chats], new_active
        except Exception as e:
            print(f"[ERROR] handle_delete: {e}", flush=True)
            return no_update, no_update, no_update

    # ---------- Image upload & store base64 ----------
    @app.callback(
        Output("upload-image-b64", "data"),
        Input("image-upload", "contents"),
        prevent_initial_call=True,
    )
    def keep_upload(b64):
        try:
            return b64
        except Exception as e:
            print(f"[ERROR] keep_upload: {e}", flush=True)
            return no_update

    # ---------- Generate caption ----------
    @app.callback(
        Output("chat-messages", "children", allow_duplicate=True),
        Output("chat-list", "children", allow_duplicate=True),
        Input("caption-btn", "n_clicks"),
        State("upload-image-b64", "data"),
        State("active-chat-id", "data"),
        prevent_initial_call=True,
    )
    def do_caption(n, b64, chat_id):
        try:
            if not n or not b64 or not chat_id:
                return no_update, no_update

            result = caption_image(b64)
            caption = result.get("caption") or "(no caption)"
            tags = result.get("tags") or []
            meta = {"image_preview": b64, "tags": tags}

            add_message(chat_id, "assistant", caption, meta=meta)
            chats = list_chats()
            messages = get_messages(chat_id)
            return messages_view(messages), [chat_item(c, chat_id) for c in chats]
        except Exception as e:
            print(f"[ERROR] do_caption: {e}", flush=True)
            return no_update, no_update

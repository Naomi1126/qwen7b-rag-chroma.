import os
import uuid
from typing import Dict, Any, List, Tuple, Optional

import gradio as gr
import requests

# CONFIG
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:9001")


# Helper para dropdown de conversaciones
def build_conv_dropdown(conv_state: Dict[str, Any], session: Dict[str, Any]):
    """
    Gradio Dropdown espera choices como:
      - lista de strings, o
      - lista de tuplas (label, value)
    """
    if conv_state is None:
        conv_state = {"by_id": {}, "order": []}

    order = conv_state.get("order", [])
    by_id = conv_state.get("by_id", {})

    choices: List[Tuple[str, str]] = []
    for cid in order:
        meta = by_id.get(cid, {}) or {}
        area = meta.get("area") or "sin área"
        title = meta.get("title") or "Nueva conversación"
        label = f"{area.upper()} - {title}"
        choices.append((label, cid))

    active_id = session.get("active_conversation_id") if session else None
    valid_ids = [v for _, v in choices]

    if active_id not in valid_ids:
        active_id = valid_ids[0] if valid_ids else None
        if session is not None:
            session["active_conversation_id"] = active_id

    return gr.update(choices=choices, value=active_id)


# LOGIN
def do_login(username: str, password: str, session: Dict[str, Any], conv_state: Dict[str, Any]):
    if not username or not password:
        raise gr.Error("Por favor ingresa usuario y contraseña.")

    try:
        resp = requests.post(
            f"{BACKEND_URL}/auth/login",
            json={"username": username, "password": password},
            timeout=10,
        )
    except requests.RequestException as e:
        raise gr.Error(f"No se pudo conectar al backend: {e}")

    if resp.status_code != 200:
        try:
            data = resp.json()
            detail = data.get("detail", resp.text)
        except Exception:
            detail = resp.text
        raise gr.Error(f"Login fallido: {detail}")

    data = resp.json()
    token = data.get("token")
    user_id = data.get("user_id")
    areas = data.get("areas", [])

    if not token or not user_id:
        raise gr.Error(
            "La respuesta de /auth/login no contiene 'token' o 'user_id'. "
            "Revisa que tu backend devuelva esos campos."
        )

    new_session = {
        "token": token,
        "user_id": user_id,
        "areas": areas,
        "active_area": areas[0] if areas else None,
        "active_conversation_id": None,
    }

    if conv_state is None:
        conv_state = {"by_id": {}, "order": []}

    # crear 1a conversación
    conv_id = str(uuid.uuid4())
    conv_state["by_id"][conv_id] = {
        "area": new_session["active_area"],
        "title": "Nueva conversación",
        "messages": [],
    }
    conv_state["order"].insert(0, conv_id)
    new_session["active_conversation_id"] = conv_id

    chat_history: List[Tuple[str, Optional[str]]] = []
    area_dd = gr.update(choices=areas, value=new_session["active_area"])
    conv_dd = build_conv_dropdown(conv_state, new_session)

    # IMPORTANTE: ocultar login y mostrar chat
    return (
        new_session,
        conv_state,
        chat_history,
        area_dd,
        conv_dd,
        gr.update(visible=False),
        gr.update(visible=True),
    )


# ENVÍO DE MENSAJES
def send_message(
    message: str,
    session: Dict[str, Any],
    conv_state: Dict[str, Any],
    area: str,
    history: List[Tuple[str, Optional[str]]],
):
    if session is None or not session.get("token"):
        raise gr.Error("No hay sesión activa. Inicia sesión nuevamente.")

    if not message or not message.strip():
        return "", history, session, conv_state, build_conv_dropdown(conv_state, session)

    areas = session.get("areas") or []
    if area not in areas:
        bot_text = (
            "No tienes acceso a esta área. "
            "Por favor contacta al administrador si crees que esto es un error."
        )
        history = history + [(message, bot_text)]
        return "", history, session, conv_state, build_conv_dropdown(conv_state, session)

    if conv_state is None:
        conv_state = {"by_id": {}, "order": []}

    active_conv_id = session.get("active_conversation_id")
    if not active_conv_id:
        active_conv_id = str(uuid.uuid4())
        session["active_conversation_id"] = active_conv_id
        conv_state["by_id"][active_conv_id] = {
            "area": area,
            "title": "Nueva conversación",
            "messages": [],
        }
        conv_state["order"].insert(0, active_conv_id)

    conv_meta = conv_state["by_id"][active_conv_id]
    conv_meta["area"] = area

    conv_meta["messages"].append({"role": "user", "content": message})
    if conv_meta["title"] == "Nueva conversación":
        first = message.strip()
        if len(first) > 40:
            first = first[:40] + "..."
        conv_meta["title"] = first

    history = history + [(message, None)]

    payload = {
        "query": message,
        "top_k": 5,
        "return_context": False,
        "return_sources": False,
    }

    headers = {"Authorization": f"Bearer {session['token']}"}

    try:
        resp = requests.post(
            f"{BACKEND_URL}/chat/{area}",
            json=payload,
            headers=headers,
            timeout=60,
        )
    except requests.RequestException as e:
        bot_text = f"Error al conectar con el backend: {e}"
        history[-1] = (message, bot_text)
        return "", history, session, conv_state, build_conv_dropdown(conv_state, session)

    if resp.status_code != 200:
        try:
            data = resp.json()
            detail = data.get("detail", resp.text)
        except Exception:
            detail = resp.text
        bot_text = f"Error desde el backend: {detail}"
        history[-1] = (message, bot_text)
        return "", history, session, conv_state, build_conv_dropdown(conv_state, session)

    data = resp.json()
    answer = data.get("answer", "")

    conv_state["by_id"][active_conv_id]["messages"].append(
        {"role": "assistant", "content": answer}
    )

    history[-1] = (message, answer)
    conv_dd = build_conv_dropdown(conv_state, session)

    return "", history, session, conv_state, conv_dd


# NUEVA CONVERSACIÓN
def new_conversation(session: Dict[str, Any], conv_state: Dict[str, Any], history, area: str):
    if session is None or not session.get("token"):
        raise gr.Error("No hay sesión activa. Inicia sesión nuevamente.")

    if conv_state is None:
        conv_state = {"by_id": {}, "order": []}

    if not area:
        area = (session.get("areas") or [None])[0]

    conv_id = str(uuid.uuid4())
    conv_state["by_id"][conv_id] = {
        "area": area,
        "title": "Nueva conversación",
        "messages": [],
    }
    conv_state["order"].insert(0, conv_id)
    session["active_conversation_id"] = conv_id

    conv_dd = build_conv_dropdown(conv_state, session)
    return [], session, conv_state, conv_dd


# CARGAR CONVERSACIÓN DESDE EL SIDEBAR
def load_conversation(conv_id: str, session: Dict[str, Any], conv_state: Dict[str, Any]):
    if not conv_id or conv_state is None:
        return [], session

    if conv_id not in conv_state.get("by_id", {}):
        return [], session

    session["active_conversation_id"] = conv_id
    conv = conv_state["by_id"][conv_id]

    history: List[Tuple[str, Optional[str]]] = []
    current_user: Optional[str] = None

    for msg in conv.get("messages", []):
        role = msg.get("role")
        content = msg.get("content", "")
        if role == "user":
            if current_user is not None:
                history.append((current_user, None))
            current_user = content
        else:
            if current_user is None:
                history.append(("", content))
            else:
                history.append((current_user, content))
                current_user = None

    if current_user is not None:
        history.append((current_user, None))

    return history, session


# CSS
CUSTOM_CSS = """<TU_CSS_IGUAL_QUE_LO_TIENES>"""
# NOTA: pega aquí tu CSS completo sin cambios. Yo lo omití para no alargar.
# (Si lo prefieres, deja tu bloque CUSTOM_CSS exactamente como lo tienes)


# UI
def build_app():
    with gr.Blocks(css=CUSTOM_CSS, theme=gr.themes.Soft()) as demo:
        session_state = gr.State({})
        conv_state = gr.State({"by_id": {}, "order": []})

        # LOGIN
        with gr.Group(visible=True, elem_id="login-page") as login_block:
            with gr.Column(elem_id="login-card"):
                with gr.Row(elem_id="login-logo-wrap"):
                    gr.Image("static/logo_empresa.png", show_label=False, height=55)

                with gr.Row(elem_id="login-user-icon"):
                    gr.Image("static/user.png", show_label=False, height=64, width=64)

                username = gr.Textbox(label="Usuario", placeholder="Usuario", elem_id="login-user")
                password = gr.Textbox(label="Contraseña", type="password", placeholder="Contraseña", elem_id="login-pass")
                login_btn = gr.Button("Entrar", variant="primary")

        # CHAT
        with gr.Group(visible=False, elem_id="app-shell") as chat_block:
            with gr.Row(elem_id="chat-row"):
                with gr.Column(scale=1, min_width=290, elem_id="sidebar"):
                    gr.Image("static/logo_empresa.png", show_label=False, height=42)

                    area_dropdown = gr.Dropdown(
                        label="",
                        choices=[],
                        interactive=True,
                        elem_id="area-dd",
                    )

                    gr.Markdown("**Historial**")
                    new_conv_btn = gr.Button("➕ Nueva conversación", elem_id="new-conv")

                    conv_dropdown = gr.Dropdown(
                        label="",
                        choices=[],
                        interactive=True,
                        elem_id="conv-dd",
                    )

                with gr.Column(scale=3, elem_id="chat-panel"):
                    with gr.Row():
                        gr.Image("static/logo_robot.png", show_label=False, height=42, width=42)

                    chatbot = gr.Chatbot(
                        label="",
                        height=520,
                        elem_id="chatbot",
                        bubble_full_width=False,
                        show_copy_button=True,
                    )

                    with gr.Row():
                        msg_box = gr.Textbox(
                            label="",
                            placeholder="Escribe tu mensaje…",
                            lines=1,
                            scale=6,
                            elem_id="msg-box",
                        )
                        send_btn = gr.Button("Enviar", variant="primary", scale=1, elem_id="send-btn")

        # EVENTOS
        login_btn.click(
            fn=do_login,
            inputs=[username, password, session_state, conv_state],
            outputs=[session_state, conv_state, chatbot, area_dropdown, conv_dropdown, login_block, chat_block],
        )

        send_btn.click(
            fn=send_message,
            inputs=[msg_box, session_state, conv_state, area_dropdown, chatbot],
            outputs=[msg_box, chatbot, session_state, conv_state, conv_dropdown],
        )

        new_conv_btn.click(
            fn=new_conversation,
            inputs=[session_state, conv_state, chatbot, area_dropdown],
            outputs=[chatbot, session_state, conv_state, conv_dropdown],
        )

        conv_dropdown.change(
            fn=load_conversation,
            inputs=[conv_dropdown, session_state, conv_state],
            outputs=[chatbot, session_state],
        )

        return demo


demo = build_app()

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        show_api=False,
        share=False,
    )

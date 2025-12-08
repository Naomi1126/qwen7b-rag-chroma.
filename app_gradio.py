# app_gradio.py
import os
import uuid
from typing import Dict, Any, List, Tuple

import gradio as gr
import requests

# -------------------------------------------------------------------
# CONFIG
# -------------------------------------------------------------------

# Backend: FastAPI RAG
# Se puede sobreescribir con la variable de entorno BACKEND_URL
BACKEND_URL = os.getenv("BACKEND_URL", "http://127.0.0.1:9001")

# Ejemplos:
# BACKEND_URL = "https://tu-backend.trycloudflare.com"
# BACKEND_URL = "https://api.miempresa.com"


# -------------------------------------------------------------------
# Helper para dropdown de conversaciones
# -------------------------------------------------------------------

def build_conv_dropdown(conv_state: Dict[str, Any], session: Dict[str, Any]):
    """
    Convierte el estado interno de conversaciones en choices para el Dropdown.

    conv_state = {
        "by_id": {
            conv_id: {
                "area": str,
                "title": str,
                "messages": [{"role": "user"/"assistant", "content": str}, ...]
            },
            ...
        },
        "order": [conv_id1, conv_id2, ...]  # más reciente primero
    }
    """
    if conv_state is None:
        conv_state = {"by_id": {}, "order": []}

    choices = []
    for cid in conv_state["order"]:
        meta = conv_state["by_id"][cid]
        area = meta.get("area") or "sin área"
        title = meta.get("title") or "Nueva conversación"
        label = f"{area.upper()} - {title}"
        choices.append({"label": label, "value": cid})

    active_id = None
    if session:
        active_id = session.get("active_conversation_id")

    conv_ids = [c["value"] for c in choices]

    if active_id not in conv_ids:
        active_id = conv_ids[0] if conv_ids else None
        if session is not None:
            session["active_conversation_id"] = active_id

    return gr.update(choices=choices, value=active_id)


# -------------------------------------------------------------------
# LOGIN
# -------------------------------------------------------------------

def do_login(
    username: str,
    password: str,
    session: Dict[str, Any],
    conv_state: Dict[str, Any],
):
    if not username or not password:
        raise gr.Error("Por favor ingresa usuario y contraseña.")

    # Llamar al backend /auth/login (JSON)
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

    # Estos nombres vienen de tu app.py (AuthLoginResponse)
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

    # Crear una primera conversación vacía
    conv_id = str(uuid.uuid4())
    conv_state["by_id"][conv_id] = {
        "area": new_session["active_area"],
        "title": "Nueva conversación",
        "messages": [],
    }
    conv_state["order"].insert(0, conv_id)
    new_session["active_conversation_id"] = conv_id

    # Chat vacío
    chat_history: List[Tuple[str, str]] = []

    # Dropdown de áreas (solo las permitidas por el backend)
    area_dd = gr.update(choices=areas, value=new_session["active_area"])

    # Dropdown de conversaciones
    conv_dropdown = build_conv_dropdown(conv_state, new_session)

    # Ocultar login, mostrar chat
    login_block_update = gr.update(visible=False)
    chat_block_update = gr.update(visible=True)

    return (
        new_session,
        conv_state,
        chat_history,
        area_dd,
        conv_dropdown,
        login_block_update,
        chat_block_update,
    )


# -------------------------------------------------------------------
# ENVÍO DE MENSAJES
# -------------------------------------------------------------------

def send_message(
    message: str,
    session: Dict[str, Any],
    conv_state: Dict[str, Any],
    area: str,
    history: List[Tuple[str, str]],
):
    if session is None or not session.get("token"):
        raise gr.Error("No hay sesión activa. Inicia sesión nuevamente.")

    if not message or not message.strip():
        # No mandamos nada si el mensaje está vacío
        return "", history, session, conv_state, build_conv_dropdown(conv_state, session)

    areas = session.get("areas") or []
    if area not in areas:
        # No se manda petición si no tiene permiso
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

    # Guardar mensaje de usuario en frontend
    conv_meta["messages"].append({"role": "user", "content": message})
    if conv_meta["title"] == "Nueva conversación":
        first = message.strip()
        if len(first) > 40:
            first = first[:40] + "..."
        conv_meta["title"] = first

    history = history + [(message, None)]

    # Payload para tu backend: /chat/{area}
    # Tu ChatRequest solo necesita "query" (top_k opcional)
    payload = {
        "query": message,
        "top_k": 5,
        "return_context": False,
        "return_sources": False,
    }

    # JWT en header Authorization: Bearer <token>
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
    # Tu ChatResponse tiene campo "answer"
    answer = data.get("answer", "")

    conv_state["by_id"][active_conv_id]["messages"].append(
        {"role": "assistant", "content": answer}
    )

    history[-1] = (message, answer)

    conv_dropdown = build_conv_dropdown(conv_state, session)

    return "", history, session, conv_state, conv_dropdown


# -------------------------------------------------------------------
# NUEVA CONVERSACIÓN
# -------------------------------------------------------------------

def new_conversation(
    session: Dict[str, Any],
    conv_state: Dict[str, Any],
    history: List[Tuple[str, str]],
    area: str,
):
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

    conv_dropdown = build_conv_dropdown(conv_state, session)

    # Limpia el chat actual
    return [], session, conv_state, conv_dropdown


# -------------------------------------------------------------------
# CARGAR CONVERSACIÓN DESDE EL SIDEBAR
# -------------------------------------------------------------------

def load_conversation(
    conv_id: str,
    session: Dict[str, Any],
    conv_state: Dict[str, Any],
):
    if not conv_id or conv_state is None:
        return [], session

    if conv_id not in conv_state.get("by_id", {}):
        return [], session

    session["active_conversation_id"] = conv_id
    conv = conv_state["by_id"][conv_id]

    # Convertir la lista de mensajes en tuplas (usuario, bot) para el Chatbot
    history: List[Tuple[str, str]] = []
    current_user = None

    for msg in conv["messages"]:
        role = msg["role"]
        content = msg["content"]
        if role == "user":
            if current_user is not None:
                history.append((current_user, None))
            current_user = content
        else:  # assistant
            if current_user is None:
                # Por si hubiera una respuesta sin user antes (no debería)
                history.append(("", content))
            else:
                history.append((current_user, content))
                current_user = None

    if current_user is not None:
        history.append((current_user, None))

    return history, session


# -------------------------------------------------------------------
# CSS para estilo azul marino y burbujas
# -------------------------------------------------------------------

CUSTOM_CSS = """
:root {
    --color-primary: #001f3f;
    --color-bg: #f3f4f6;
}

.gradio-container {
    font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    background: var(--color-bg);
}

/* Header */
#header {
    background: white;
    border-radius: 12px;
    padding: 0.75rem 1rem;
    box-shadow: 0 10px 25px rgba(15, 23, 42, 0.08);
    margin-bottom: 1rem;
}

/* Chatbot burbujas */
#chatbot .message.user {
    justify-content: flex-end;
}

#chatbot .message.user .bubble {
    background: var(--color-primary);
    color: white;
}

#chatbot .message.bot {
    justify-content: flex-start;
}

#chatbot .message.bot .bubble {
    background: white;
    color: #111827;
}

/* Sidebar de conversaciones */
#sidebar {
    background: white;
    border-radius: 12px;
    padding: 0.75rem 1rem;
    box-shadow: 0 10px 25px rgba(15, 23, 42, 0.08);
}

/* Panel de chat */
#chat-panel {
    background: white;
    border-radius: 12px;
    padding: 0.75rem 1rem;
    box-shadow: 0 10px 25px rgba(15, 23, 42, 0.08);
}
"""


# -------------------------------------------------------------------
# Construcción de la interfaz Gradio
# -------------------------------------------------------------------

def build_app():
    with gr.Blocks(css=CUSTOM_CSS, theme=gr.themes.Soft()) as demo:
        session_state = gr.State({})
        conv_state = gr.State({"by_id": {}, "order": []})

        # HEADER CON LOGOS
        with gr.Row(elem_id="header"):
            with gr.Column(scale=1, min_width=120):
                gr.Image(
                    "static/logo_empresa.png",
                    show_label=False,
                    height=70,
                    width=120,
                )
            with gr.Column(scale=3):
                gr.Markdown(
                    "## Chatbot Corporativo\n"
                    "Interfaz tipo ChatGPT/Gemini con autenticación y áreas por usuario."
                )
            with gr.Column(scale=1, min_width=80):
                gr.Image(
                    "static/logo_robot.png",
                    show_label=False,
                    height=70,
                    width=70,
                )

        # BLOQUE DE LOGIN
        with gr.Group(visible=True) as login_block:
            gr.Markdown("### Iniciar sesión")
            with gr.Row():
                username = gr.Textbox(
                    label="Usuario o correo",
                    placeholder="tu_usuario",
                )
                password = gr.Textbox(
                    label="Contraseña",
                    type="password",
                    placeholder="••••••••",
                )
            login_btn = gr.Button("Iniciar sesión", variant="primary")

        # BLOQUE DE CHAT (oculto hasta que haya sesión)
        with gr.Group(visible=False) as chat_block:
            with gr.Row():
                # SIDEBAR DE HISTORIALES
                with gr.Column(scale=1, min_width=260, elem_id="sidebar"):
                    gr.Markdown("### Conversaciones")
                    new_conv_btn = gr.Button("➕ Nueva conversación")
                    conv_dropdown = gr.Dropdown(
                        label="Historial",
                        choices=[],
                        interactive=True,
                    )

                # PANEL PRINCIPAL DE CHAT
                with gr.Column(scale=3, elem_id="chat-panel"):
                    area_dropdown = gr.Dropdown(
                        label="Área",
                        choices=[],
                        interactive=True,
                    )
                    chatbot = gr.Chatbot(
                        label="Chat",
                        height=500,
                        elem_id="chatbot",
                        bubble_full_width=False,
                        show_copy_button=True,
                    )
                    with gr.Row():
                        msg_box = gr.Textbox(
                            label="Escribe tu mensaje",
                            placeholder="Pregunta algo al chatbot...",
                            lines=3,
                            scale=4,
                        )
                        send_btn = gr.Button("Enviar", variant="primary", scale=1)

        # LÓGICA DE EVENTOS

        # Login
        login_btn.click(
            fn=do_login,
            inputs=[username, password, session_state, conv_state],
            outputs=[
                session_state,   # actualiza sesión
                conv_state,      # actualiza conv_state
                chatbot,         # limpia chat
                area_dropdown,   # llena áreas
                conv_dropdown,   # llena historiales
                login_block,     # oculta login
                chat_block,      # muestra chat
            ],
        )

        # Enviar mensaje
        send_btn.click(
            fn=send_message,
            inputs=[msg_box, session_state, conv_state, area_dropdown, chatbot],
            outputs=[msg_box, chatbot, session_state, conv_state, conv_dropdown],
        )

        # Nueva conversación
        new_conv_btn.click(
            fn=new_conversation,
            inputs=[session_state, conv_state, chatbot, area_dropdown],
            outputs=[chatbot, session_state, conv_state, conv_dropdown],
        )

        # Seleccionar conversación del historial
        conv_dropdown.change(
            fn=load_conversation,
            inputs=[conv_dropdown, session_state, conv_state],
            outputs=[chatbot, session_state],
        )

        return demo


demo = build_app()

if __name__ == "__main__":
    # IMPORTANTE: escucha en 0.0.0.0 y puerto 7860
    demo.queue()
    demo.launch(server_name="0.0.0.0", server_port=7860)

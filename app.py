from openai import OpenAI
import streamlit as st
from dotenv import load_dotenv
import os
import shelve
import time

load_dotenv()

st.title("EDEKA Store Reviews Assistant")

USER_AVATAR = "👤"
BOT_AVATAR = "🤖"
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
file_id = os.getenv("File_ID")
assistant_id = os.getenv("Assistant_ID")

# Ensure openai_model is initialized in session state
if "openai_model" not in st.session_state:
    st.session_state["openai_model"] = "gpt-4o-mini"


if os.getenv("File_ID") is None:
    file = client.files.create(
        file=open("edeka_store_reviews_theme_melt.csv", "rb"), purpose="assistants"
    )
    with open(".env", "a") as env_file:
        env_file.write(f"\nFile_ID={file.id}")
    file_id = file.id
else:
    file_id = os.getenv("File_ID")

if os.getenv("Assistant_ID") is None:
    assistant = client.beta.assistants.create(
        name="Data Creator",
        description=(
            "You are great at creating beautiful data visualizations."
            + "You analyze data present in .csv files, understand trends,"
            + "and come up with data visualizations relevant to those trends."
            + "You also share a brief text summary of the trends observed."
        ),
        model="gpt-4o-mini",
        tools=[{"type": "code_interpreter"}],
        tool_resources={"code_interpreter": {"file_ids": [file_id]}},
    )
    with open(".env", "a") as env_file:
        env_file.write(f"\nAssistant_ID={assistant.id}")
    assistant_id = assistant.id
else:
    assistant_id = os.getenv("Assistant_ID")


# Load chat history from shelve file
def load_chat_history():
    with shelve.open("chat_history") as db:
        return db.get("messages", [])


# Save chat history to shelve file
def save_chat_history(messages):
    with shelve.open("chat_history") as db:
        db["messages"] = messages


# Add thread_id load/save functions and initialization
def load_thread_id():
    with shelve.open("chat_history") as db:
        return db.get("thread_id")


def save_thread_id(tid):
    with shelve.open("chat_history") as db:
        db["thread_id"] = tid


if "thread_id" not in st.session_state:
    tid = load_thread_id()
    if not tid:
        thread = client.beta.threads.create()
        tid = thread.id
        save_thread_id(tid)
    st.session_state.thread_id = tid

# Initialize or load chat history
if "messages" not in st.session_state:
    st.session_state.messages = load_chat_history()

# Sidebar with a button to delete chat history
with st.sidebar:
    if st.button("Chat History Löschen"):
        st.session_state.messages = []
        save_chat_history([])
    # Add new thread button
    if st.button("Neuer Thread"):
        thread = client.beta.threads.create()
        st.session_state.thread_id = thread.id
        save_thread_id(thread.id)

# Display chat messages
for message in st.session_state.messages:
    avatar = USER_AVATAR if message["role"] == "user" else BOT_AVATAR
    with st.chat_message(message["role"], avatar=avatar):
        st.markdown(message["content"])

if prompt := st.chat_input(
    "Hi, ich supporte dich bei allen Fragen zu den EDEKA Maps bewertungen!"
):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar=USER_AVATAR):
        st.markdown(prompt)

    # Send user message to the thread using stored thread_id
    message = client.beta.threads.messages.create(
        thread_id=st.session_state.thread_id,
        role="user",
        content=prompt,
    )

    # Run the assistant using stored thread_id
    run = client.beta.threads.runs.create(
        thread_id=st.session_state.thread_id,
        assistant_id=assistant_id,
    )

    # Wait for the assistant's response
    with st.chat_message("assistant", avatar=BOT_AVATAR):
        message_placeholder = st.markdown("Ich denke...")
        while True:
            run_status = client.beta.threads.runs.retrieve(
                thread_id=st.session_state.thread_id,
                run_id=run.id,
            )
            if run_status.status == "completed":
                break
            time.sleep(1)  # Avoid API spamming

        # Retrieve the assistant's last response
        messages = client.beta.threads.messages.list(
            thread_id=st.session_state.thread_id
        )

        full_response = ""
        for msg in messages.data:
            if msg.role == "assistant":
                full_response = msg.content[0].text.value
                break

        message_placeholder.markdown(full_response)

    st.session_state.messages.append({"role": "assistant", "content": full_response})

# Save chat history after each interaction
save_chat_history(st.session_state.messages)

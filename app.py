import streamlit as st
from google import genai
from google.genai import types
from twilio.rest import Client as TwilioClient


# ============================================================
# CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="MacroSnap",
    page_icon="🥗",
    layout="centered"
)

# Use a currently available Flash model.
MODEL_NAME = "gemini-3.8-flash"


# ============================================================
# SECRETS
# ============================================================

GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]

TWILIO_ACCOUNT_SID = st.secrets["TWILIO_ACCOUNT_SID"]
TWILIO_AUTH_TOKEN = st.secrets["TWILIO_AUTH_TOKEN"]

# Twilio WhatsApp Sandbox number
TWILIO_WHATSAPP_FROM = st.secrets.get(
    "TWILIO_WHATSAPP_FROM",
    "whatsapp:+14155238886"
)


# ============================================================
# CLIENTS
# ============================================================

@st.cache_resource
def get_gemini_client():
    return genai.Client(api_key=GEMINI_API_KEY)


@st.cache_resource
def get_twilio_client():
    return TwilioClient(
        TWILIO_ACCOUNT_SID,
        TWILIO_AUTH_TOKEN
    )


gemini_client = get_gemini_client()
twilio_client = get_twilio_client()


# ============================================================
# PHONE NUMBER
# ============================================================

def normalize_phone_number(number):
    """
    Converts common formats into E.164 format.

    Example:
        +91 9246117788
        +91-9246117788
        +919246117788

    becomes:

        +919246117788
    """

    number = number.strip()

    # Remove common formatting characters
    number = number.replace(" ", "")
    number = number.replace("-", "")
    number = number.replace("(", "")
    number = number.replace(")", "")

    # Add + if missing
    if not number.startswith("+"):
        number = "+" + number

    return number


# ============================================================
# GEMINI
# ============================================================

def create_gemini_chat():
    return gemini_client.chats.create(
        model=MODEL_NAME,
        config=types.GenerateContentConfig(
            system_instruction="""
You are MacroSnap, an AI nutrition assistant.

Your job is to analyze meals from photos and answer nutrition questions.

When a user uploads a meal photo:

1. Identify the visible food items.
2. Estimate the approximate serving size.
3. Estimate calories for each major item.
4. Estimate protein, carbohydrates and fat.
5. Give a total estimated calorie count.
6. Give total estimated macros.
7. Clearly state that image-based nutrition values are estimates.
8. Do not pretend the values are exact.

Use simple language.

For meal analysis, use this format:

🍽️ Meal Analysis

1. Food item — estimated quantity
   Calories: XX kcal
   Protein: XX g
   Carbs: XX g
   Fat: XX g

2. Food item — estimated quantity
   Calories: XX kcal
   Protein: XX g
   Carbs: XX g
   Fat: XX g

📊 Estimated Total
Calories: XXX kcal
Protein: XX g
Carbs: XX g
Fat: XX g

Note: These values are estimates based on the image and may vary depending on ingredients, preparation method and portion size.
"""
        )
    )


def ask_gemini(parts):
    try:
        response = st.session_state.chat.send_message(parts)

        if response and response.text:
            return response.text

        return "Sorry, I couldn't generate a nutrition analysis."

    except Exception as error:
        return f"Sorry, Gemini encountered an error:\n\n{error}"


# ============================================================
# WHATSAPP MESSAGE
# ============================================================

def clean_whatsapp_text(text):
    if not text:
        return "No nutrition summary available."

    # WhatsApp message cleanup
    text = text.strip()

    # Keep message at a reasonable size
    if len(text) > 3500:
        text = text[:3500] + "\n\n..."

    return text


def send_whatsapp(to_number, user_name, summary):

    try:
        # Normalize recipient number
        to_number = normalize_phone_number(to_number)

        whatsapp_to = f"whatsapp:{to_number}"

        # Clean Gemini response
        summary = clean_whatsapp_text(summary)

        message_body = (
            f"🥗 MacroSnap Nutrition Summary\n\n"
            f"Hi {user_name}!\n\n"
            f"{summary}\n\n"
            f"— MacroSnap"
        )

        # Send free-form WhatsApp message.
        #
        # IMPORTANT:
        # This works during the WhatsApp 24-hour
        # customer-service window.
        message = twilio_client.messages.create(
            from_=TWILIO_WHATSAPP_FROM,
            to=whatsapp_to,
            body=message_body
        )

        return True, message.sid, message.status

    except Exception as error:
        return False, str(error), None


# ============================================================
# RENDER CHAT MESSAGE
# ============================================================

def render_message(message):

    with st.chat_message(message["role"]):

        if message["kind"] == "text":
            st.markdown(message["content"])

        elif message["kind"] == "image":
            st.image(message["content"])


def add_message(role, kind, content):

    st.session_state.messages.append(
        {
            "role": role,
            "kind": kind,
            "content": content
        }
    )

    render_message(
        st.session_state.messages[-1]
    )


# ============================================================
# STEP 1 — ONBOARDING
# ============================================================

if "onboarded" not in st.session_state:

    st.title("🥗 MacroSnap")

    st.caption(
        "Snap it. Track it. Text yourself the results."
    )

    st.divider()

    with st.form("onboarding_form"):

        name = st.text_input(
            "Your name",
            placeholder="Enter your name"
        )

        whatsapp_number = st.text_input(
            "WhatsApp number",
            placeholder="+91XXXXXXXXXX",
            help="Enter your WhatsApp number with country code."
        )

        submitted = st.form_submit_button(
            "Let's go 🚀",
            use_container_width=True
        )

    if submitted:

        if not name.strip():

            st.warning(
                "Please enter your name."
            )

        elif not whatsapp_number.strip():

            st.warning(
                "Please enter your WhatsApp number."
            )

        else:

            normalized_number = normalize_phone_number(
                whatsapp_number
            )

            # Basic validation
            if len(normalized_number) < 10:

                st.error(
                    "Please enter a valid international phone number."
                )

            else:

                st.session_state.name = name.strip()

                st.session_state.whatsapp_number = (
                    normalized_number
                )

                st.session_state.chat = create_gemini_chat()

                st.session_state.messages = []

                st.session_state.onboarded = True

                st.rerun()

    st.stop()


# ============================================================
# STEP 2 — MAIN HEADER
# ============================================================

header_col, button_col = st.columns(
    [5, 2],
    vertical_alignment="center"
)


with header_col:

    st.title("🥗 MacroSnap")


with button_col:

    # Enable WhatsApp button once the user has interacted
    # with the assistant.
    send_disabled = len(
        st.session_state.messages
    ) <= 1

    if st.button(
        "📤 Send to WhatsApp",
        disabled=send_disabled,
        use_container_width=True
    ):

        with st.spinner(
            "Preparing your nutrition summary..."
        ):

            summary = ask_gemini(
                [
                    """
Create a concise daily nutrition summary
based on the meals discussed in this conversation.

Include:

Calories
Protein
Carbohydrates
Fat

Mention the main meals/foods analyzed.

Keep it concise enough for WhatsApp.
"""
                ]
            )

        with st.spinner(
            "Sending to WhatsApp..."
        ):

            success, info, status = send_whatsapp(
                st.session_state.whatsapp_number,
                st.session_state.name,
                summary
            )

        if success:

            st.success(
                f"Message submitted to WhatsApp 📲"
            )

            st.caption(
                f"Twilio status: {status} | Message ID: {info}"
            )

        else:

            st.error(
                f"Couldn't send that:\n\n{info}"
            )


# ============================================================
# USER INFORMATION
# ============================================================

st.caption(
    f"Logged in as {st.session_state.name} "
    f"• WhatsApp: {st.session_state.whatsapp_number}"
)

st.divider()


# ============================================================
# WELCOME MESSAGE
# ============================================================

if not st.session_state.messages:

    welcome_message = f"""
👋 Hi {st.session_state.name}!

I'm **MacroSnap** 🥗

You can:

📸 Upload a photo of your meal  
🍽️ Get estimated calories  
💪 Get protein, carbs and fat  
💬 Ask nutrition questions  
📲 Send your nutrition summary to WhatsApp

Upload your first meal photo below!
"""

    add_message(
        "assistant",
        "text",
        welcome_message
    )

else:

    for message in st.session_state.messages:

        render_message(message)


# ============================================================
# CHAT INPUT
# ============================================================

user_input = st.chat_input(
    "Ask a question, or attach a photo of your meal",
    accept_file=True,
    file_type=[
        "jpg",
        "jpeg",
        "png"
    ]
)


# ============================================================
# PROCESS USER INPUT
# ============================================================

if user_input:

    photo = (
        user_input.files[0]
        if user_input.files
        else None
    )

    text = user_input.text

    parts = []


    # --------------------------------------------------------
    # IMAGE
    # --------------------------------------------------------

    if photo is not None:

        photo_bytes = photo.getvalue()

        # Show uploaded image
        add_message(
            "user",
            "image",
            photo_bytes
        )

        # Send image to Gemini
        parts.append(
            types.Part.from_bytes(
                data=photo_bytes,
                mime_type=photo.type
            )
        )


    # --------------------------------------------------------
    # TEXT
    # --------------------------------------------------------

    if text:

        add_message(
            "user",
            "text",
            text
        )

        parts.append(text)


    # --------------------------------------------------------
    # IMAGE WITHOUT TEXT
    # --------------------------------------------------------

    elif photo is not None:

        parts.append(
            """
Analyze this meal.

Identify the food items and estimate:

- Serving size
- Calories
- Protein
- Carbohydrates
- Fat

Then provide an estimated total for the entire meal.

Clearly mention that the values are estimates.
"""
        )


    # --------------------------------------------------------
    # GEMINI
    # --------------------------------------------------------

    if parts:

        with st.spinner(
            "🥗 Analyzing your meal..."
        ):

            answer = ask_gemini(parts)

        add_message(
            "assistant",
            "text",
            answer
        )